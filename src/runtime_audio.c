/* libSceAudioOut on SDL3 audio streams. sceAudioOutOutput returns once per
 * buffer period on a steady clock, like PS4 hardware: FMOD's output thread
 * reads 256-frame slots out of its mixer's 512-frame ring, and returning in
 * bursts (whenever the device pulls a quantum) lets it overtake the mixer and
 * play stale halves - a click every 10.7 ms. The lowest SDL queue level of
 * each window is steered to two buffers (silence prefill on underrun, ±3%
 * cadence corrections), which also absorbs device clock drift. Without an audio device (headless runs, BB_AUDIO=none)
 * ports only follow the clock. */
#define _GNU_SOURCE
#include "runtime.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <time.h>
#include <math.h>
#include <SDL3/SDL.h>
#ifdef _WIN32
#include <windows.h>
#include "log.h"
#endif

#define PORTS 25
/* The guest's audio thread writes here; a dedicated feeder thread drains the ring into the SDL
 * device. 96000 frames = 2.0 s at 48 kHz: an audio buffer cushion (shader compile, stage load)
 * drains the cushion instead of starving WASAPI/SDL. */
#define AUDIO_RING_FRAMES 96000
#define FEEDER_MAX_FRAMES 4096
#define AUDIO_MAX_QUEUE_FRAMES 24000 /* ~500 ms at 48 kHz max latency cap */
#define MOVIE_RING_FRAMES 96000      /* dedicated AvPlayer ring: 2 s of stereo float */
#define FADE_FRAMES 64
#define ERR_NOT_OPENED ((int32_t)0x80260001)
#define ERR_INVALID_PORT ((int32_t)0x80260003)
#define ERR_INVALID_POINTER ((int32_t)0x80260004)
#define ERR_PORT_FULL ((int32_t)0x80260005)
#define ERR_INVALID_SIZE ((int32_t)0x80260006)
#define ERR_INVALID_FORMAT ((int32_t)0x80260007)
#define ERR_INVALID_FREQ ((int32_t)0x80260008)
#define ERR_INVALID_VOLUME ((int32_t)0x80260009)
#define ERR_INVALID_TYPE ((int32_t)0x8026000A)
#define ERR_ALREADY_INIT ((int32_t)0x8026000E)
#define ERR_NOT_INIT ((int32_t)0x8026000F)
#define VOLUME_0DB 32768

typedef struct {
    int used, type, channels, is_float, frames, sample_bytes, std_layout;
    int32_t volume[8];
    SDL_AudioStream *stream;
    uint64_t next_deadline_ns; /* next return of sceAudioOutOutput */
    uint64_t last_output_us;
    pthread_mutex_t lock;
    FILE *dump;                     /* BB_AUDIO_DUMP: raw converted PCM per port */
    int stats;
    uint64_t stat_start_ns, stat_last_ns, stat_max_gap_ns; /* BB_AUDIO_STATS */
    unsigned stat_starved, stat_buffers; int stat_min_queued;
    uint32_t call_count;
    /* Producer/consumer ring (stereo float) and the feeder thread that owns the SDL stream. */
    float ring[AUDIO_RING_FRAMES * 2];
    uint32_t ring_read, ring_write, ring_avail;
    uint32_t prefill_frames;        /* latency cushion: ~50 ms (BB_AUDIO_PREFILL_MS) */
    int primed;                     /* 1 once initial prefill reached; 0 on complete empty */
    pthread_t feeder;
    int feeder_running, feeder_stop;
#ifdef _WIN32
    HANDLE mmcss_handle;
    DWORD mmcss_task_idx;
#endif
    int silent, fade_pos;           /* underrun recovery: ramp to zero, then ramp new data in */
    float last_l, last_r, fade_l, fade_r;
    unsigned underruns;
} Port;
typedef struct { uint16_t output; uint8_t channel, reserved; int16_t volume; uint16_t reroute; uint64_t flag, reserved64[2]; } PortState;
_Static_assert(sizeof(PortState)==32,"AudioOut port state layout");

static pthread_mutex_t table_lock=PTHREAD_MUTEX_INITIALIZER;
static Port ports[PORTS];
static int initialized, sdl_ready=-1;
static size_t buffers_out, ports_opened;
/* Movie (AvPlayer) audio has its own producer/consumer ring. It must never share ports[0]:
 * sceAudioOutOutput also writes that ring every 5.33 ms (NGS2 silence or game audio), which
 * interleaved with the movie samples and made the opening song sound like a broken cassette.
 * Exactly one feeder (the first opened port, normally port 0) mixes this ring into its output. */
static float s_movie_ring[MOVIE_RING_FRAMES*2];
static uint32_t s_movie_read, s_movie_write, s_movie_avail;
static pthread_mutex_t s_movie_lock=PTHREAD_MUTEX_INITIALIZER;
static int s_movie_port=-1;
/* AvPlayer owns the movie soundtrack. While it is playing, the game's main/BGM ports may also
 * feed the same music; mixing both made the opening sound doubled. */
static int s_movie_active;
static uint64_t s_movie_last_write_ns;

static uint64_t now_ns(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t); return (uint64_t)t.tv_sec*1000000000u+(uint64_t)t.tv_nsec; }
/* True while AvPlayer audio is queued or was written less than 1.5 s ago. The timeout keeps a
 * stopped/never-closed player from muting in-game BGM forever; an explicit close clears it. */
static int movie_audio_active(void) {
    pthread_mutex_lock(&s_movie_lock);
    const uint64_t now=now_ns();
    const int active=s_movie_active &&
                     (s_movie_avail>0 ||
                      (s_movie_last_write_ns && now-s_movie_last_write_ns<1500000000ull));
    pthread_mutex_unlock(&s_movie_lock);
    return active;
}
void runtime_audio_stop_movie(void) {
    LOG_INFO("audio", "Video/Audio movie stream stopped");
    pthread_mutex_lock(&s_movie_lock);
    s_movie_active=0;
    s_movie_last_write_ns=0;
    s_movie_read=s_movie_write=s_movie_avail=0;
    pthread_mutex_unlock(&s_movie_lock);
}
static void sleep_until(uint64_t deadline) {
#ifdef _WIN32
    /* winpthreads' clock_nanosleep only takes CLOCK_REALTIME (EINVAL otherwise). */
    for (uint64_t now=now_ns(); now<deadline; now=now_ns()) compat_sleep_ns(deadline-now);
#else
    struct timespec t={(time_t)(deadline/1000000000u),(long)(deadline%1000000000u)};
    while (clock_nanosleep(CLOCK_MONOTONIC,TIMER_ABSTIME,&t,NULL)) {}
#endif
}
static int sdl_audio(void) {
    if (sdl_ready<0) {
        const char *mode=getenv("BB_AUDIO");
        const char *mute=getenv("BB_MUTE");
        int disabled = (mute && (strcmp(mute,"1")==0 || strcmp(mute,"true")==0)) ||
                       (mode && (strcmp(mode,"none")==0 || strcmp(mode,"off")==0 ||
                                 strcmp(mode,"0")==0 || strcmp(mode,"mute")==0 ||
                                 strcmp(mode,"false")==0));
        sdl_ready = !disabled && SDL_InitSubSystem(SDL_INIT_AUDIO);
        printf("Runtime: audio backend %s\n", sdl_ready ? SDL_GetCurrentAudioDriver() : "timer (silent / muted)");
    }
    return sdl_ready;
}
static int port_range(int type, int *first, int *last) {
    switch (type) {
    case 0: *first=0; *last=7; return 1;      /* main */
    case 1: *first=8; *last=8; return 1;      /* bgm */
    case 2: *first=9; *last=12; return 1;     /* voice */
    case 3: *first=13; *last=16; return 1;    /* personal */
    case 4: *first=17; *last=20; return 1;    /* pad speaker */
    case 126: *first=21; *last=22; return 1;  /* audio3d */
    case 127: *first=23; *last=24; return 1;  /* aux */
    default: return 0;
    }
}
static Port *port_of(int32_t handle, int32_t *error) {
    int id=handle & 0xff;
    if ((handle & 0x3f000000)!=0x20000000 || id>=PORTS) { *error=ERR_INVALID_PORT; return NULL; }
    if (!ports[id].used) { *error=ERR_NOT_OPENED; return NULL; }
    return &ports[id];
}
/* Dedicated feeder: keeps the SDL stream at four periods, takes PCM from the ring, and when the
 * ring runs dry keeps the device fed with silence so WASAPI never tears the stream down. A short
 * ramp stops the transitions from clicking. */
#ifdef _WIN32
typedef enum _AVRT_PRIORITY {
    AVRT_PRIORITY_LOW = -1,
    AVRT_PRIORITY_NORMAL = 0,
    AVRT_PRIORITY_HIGH = 1,
    AVRT_PRIORITY_CRITICAL = 2
} AVRT_PRIORITY;
typedef HANDLE (WINAPI *pfnAvSetMmThreadCharacteristicsW)(LPCWSTR, LPDWORD);
typedef BOOL (WINAPI *pfnAvRevertMmThreadCharacteristics)(HANDLE);
typedef BOOL (WINAPI *pfnAvSetMmThreadPriority)(HANDLE, AVRT_PRIORITY);
static pfnAvSetMmThreadCharacteristicsW s_AvSetMmThreadCharacteristicsW = NULL;
static pfnAvRevertMmThreadCharacteristics s_AvRevertMmThreadCharacteristics = NULL;
static pfnAvSetMmThreadPriority s_AvSetMmThreadPriority = NULL;
static int s_avrt_loaded = 0;

static void init_avrt_symbols(void) {
    if (s_avrt_loaded) return;
    s_avrt_loaded = 1;
    HMODULE hAvrt = LoadLibraryA("avrt.dll");
    if (hAvrt) {
        s_AvSetMmThreadCharacteristicsW = (pfnAvSetMmThreadCharacteristicsW)(void(*)(void))GetProcAddress(hAvrt, "AvSetMmThreadCharacteristicsW");
        s_AvRevertMmThreadCharacteristics = (pfnAvRevertMmThreadCharacteristics)(void(*)(void))GetProcAddress(hAvrt, "AvRevertMmThreadCharacteristics");
        s_AvSetMmThreadPriority = (pfnAvSetMmThreadPriority)(void(*)(void))GetProcAddress(hAvrt, "AvSetMmThreadPriority");
    }
}
#endif

static void *feeder_main(void *arg) {
    Port *p=(Port *)arg;
#ifdef _WIN32
    __try {
#endif
    SDL_SetCurrentThreadPriority(SDL_THREAD_PRIORITY_TIME_CRITICAL);
#ifdef _WIN32
    init_avrt_symbols();
    const char *mmcss_status = "unavailable";
    p->mmcss_handle = NULL;
    p->mmcss_task_idx = 0;
    if (s_AvSetMmThreadCharacteristicsW) {
        p->mmcss_handle = s_AvSetMmThreadCharacteristicsW(L"Pro Audio", &p->mmcss_task_idx);
        if (p->mmcss_handle) {
            mmcss_status = "ok";
            if (s_AvSetMmThreadPriority) s_AvSetMmThreadPriority(p->mmcss_handle, AVRT_PRIORITY_CRITICAL);
        } else {
            fprintf(stderr, "[PRIORITY] Warning: AvSetMmThreadCharacteristicsW failed (%lu)\n", GetLastError());
            mmcss_status = "failed";
        }
    }
    if (!p->mmcss_handle) {
        SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_TIME_CRITICAL);
    }
    fprintf(stderr, "[PRIORITY] thread_audio=%s mmcss=%s\n", p->mmcss_handle ? "pro_audio" : "time_critical", mmcss_status);
#endif
    float *mix=(float *)malloc(FEEDER_MAX_FRAMES*2*sizeof(float));
    if (!mix) return NULL;
    for (;;) {
        pthread_mutex_lock(&p->lock);
        int stop=p->feeder_stop;
        SDL_AudioStream *stream=p->stream;
        int period=p->frames>0 ? p->frames : 256;
        int target=period*4;
        if (target<1024) target=1024;
        if (target>FEEDER_MAX_FRAMES) target=FEEDER_MAX_FRAMES;
        int need=0;
        if (stream && !stop) {
            int queued=SDL_GetAudioStreamQueued(stream)/(2*(int)sizeof(float));
            need=target-queued;
            if (need<0) need=0;
            if (need>FEEDER_MAX_FRAMES) need=FEEDER_MAX_FRAMES;
        }
        /* Wait until initial prefill cushion exists before starting playback;
         * once primed, play continuously as long as audio is available. */
        if (!p->primed && p->ring_avail >= p->prefill_frames) {
            p->primed = 1;
        }
        int produced=0;
        /* One feeder owns the movie ring (normally port 0). Mixing here, after the port ring
         * sample is chosen, keeps the movie independent from sceAudioOutOutput's cadence and
         * silence writes; either source may be empty without disturbing the other. */
        pthread_mutex_lock(&s_movie_lock);
        const int movie_here = (s_movie_port >= 0 && p == &ports[s_movie_port] && need > 0);
        for (int i=0;i<need;++i) {
            float l, r;
            if (p->primed && p->ring_avail > 0) {
                uint32_t rp=p->ring_read;
                l=p->ring[rp*2+0]; r=p->ring[rp*2+1];
                p->ring_read=(rp+1)%AUDIO_RING_FRAMES;
                --p->ring_avail;
                if (p->silent) { p->silent=0; p->fade_pos=0; }
                if (p->fade_pos<FADE_FRAMES) {
                    float g=(float)p->fade_pos/(float)FADE_FRAMES;
                    l*=g; r*=g; ++p->fade_pos;
                }
            } else {
                if (p->ring_avail == 0) {
                    p->primed = 0;
                }
                if (!p->silent) {
                    p->silent=1; p->fade_pos=0;
                    p->fade_l=p->last_l; p->fade_r=p->last_r;
                    ++p->underruns;
                }
                if (p->fade_pos<FADE_FRAMES) {
                    float g=1.0f-(float)p->fade_pos/(float)FADE_FRAMES;
                    l=p->fade_l*g; r=p->fade_r*g; ++p->fade_pos;
                } else {
                    l=r=0.0f;
                }
            }
            if (movie_here && s_movie_avail > 0) {
                const uint32_t mr=s_movie_read;
                l+=s_movie_ring[mr*2+0];
                r+=s_movie_ring[mr*2+1];
                s_movie_read=(mr+1)%MOVIE_RING_FRAMES;
                --s_movie_avail;
                if (l>1.0f) l=1.0f; else if (l<-1.0f) l=-1.0f;
                if (r>1.0f) r=1.0f; else if (r<-1.0f) r=-1.0f;
            }
            p->last_l=l; p->last_r=r;
            mix[i*2+0]=l; mix[i*2+1]=r;
            produced=i+1;
        }
        pthread_mutex_unlock(&s_movie_lock);
        pthread_mutex_unlock(&p->lock);
        if (stop) break;
        if (produced>0 && stream) SDL_PutAudioStreamData(stream,mix,produced*2*(int)sizeof(float));
        compat_sleep_ns(4*1000000u);
    }
#ifdef _WIN32
    if (p->mmcss_handle && s_AvRevertMmThreadCharacteristics) {
        s_AvRevertMmThreadCharacteristics(p->mmcss_handle);
        p->mmcss_handle = NULL;
    }
#endif
    free(mix);
#ifdef _WIN32
    } __except(fatal_exception(GetExceptionInformation())) {
    }
#endif
    return NULL;
}

static ABI int32_t audio_init(void) {
    LOG_INFO("audio", "Audio subsystem initializing (sceAudioOutInit)");
    pthread_mutex_lock(&table_lock);
    int32_t r=initialized ? ERR_ALREADY_INIT : 0;
    initialized=1;
    pthread_mutex_unlock(&table_lock);
    return r;
}
static ABI int32_t audio_open(int32_t user, int32_t type, int32_t index, uint32_t length, uint32_t freq, uint32_t param) {
    (void)user; (void)index;
    if (!initialized) return ERR_NOT_INIT;
    if (!length || length>2048 || (length & 0xff)) return ERR_INVALID_SIZE;
    if (freq!=48000) return ERR_INVALID_FREQ;
    uint32_t format=param & 0xff;
    if (format>7) return ERR_INVALID_FORMAT;
    int first, last;
    if (!port_range(type,&first,&last)) return ERR_INVALID_TYPE;
    static const int channels[8]={1,2,8,1,2,8,8,8};
    pthread_mutex_lock(&table_lock);
    int id=-1;
    for (int i=first;i<=last;++i) if (!ports[i].used) { id=i; break; }
    if (id<0) { pthread_mutex_unlock(&table_lock); return ERR_PORT_FULL; }
    Port *p=&ports[id];
    memset(p,0,sizeof(*p));
    pthread_mutex_init(&p->lock,NULL);
    p->used=1; p->type=type; p->channels=channels[format]; p->is_float=format>=3 && format!=6;
    p->sample_bytes=p->is_float ? 4 : 2; p->frames=(int)length; p->std_layout=format>=6;
    /* Responsive low-latency prefill: 50 ms default for crisp instant audio reaction.
     * BB_AUDIO_PREFILL_MS overrides; capped at 120 ms to prevent perceptible delay. */
    {
        const char *ms=getenv("BB_AUDIO_PREFILL_MS");
        long value=ms ? strtol(ms,NULL,10) : 50;
        if (value<0) value=0;
        if (value>120) value=120;
        p->prefill_frames=(uint32_t)((uint64_t)value*48000u/1000u);
    }
    for (int c=0;c<8;++c) p->volume[c]=VOLUME_0DB;
    if (sdl_audio()) {
        SDL_AudioSpec spec={SDL_AUDIO_F32, 2, 48000};
        p->stream=SDL_OpenAudioDeviceStream(SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK,&spec,NULL,NULL);
        if (p->stream) {
            SDL_ResumeAudioStreamDevice(p->stream);
            p->feeder_stop=0;
            pthread_mutex_lock(&s_movie_lock);
            if (s_movie_port < 0) s_movie_port = id; /* exactly one feeder mixes movie audio */
            pthread_mutex_unlock(&s_movie_lock);
            p->feeder_running=pthread_create(&p->feeder,NULL,feeder_main,p)==0;
            if (!p->feeder_running)
                fprintf(stderr,"Runtime: audio feeder thread failed; port %d pushes directly\n",id);
        }
        else fprintf(stderr,"Runtime: SDL audio stream failed (%s); port %d uses the timer sink\n",SDL_GetError(),id);
    }
    LOG_INFO("audio", "Audio port %d opened (handle=0x%08x, type=%d, ch=%d, rate=%u, frames=%d)",
             id, (type<<16) | id | 0x20000000, type, p->channels, freq, p->frames);
    p->stats=getenv("BB_AUDIO_STATS")!=NULL;
    const char *dump=getenv("BB_AUDIO_DUMP");
    if (dump) {
        char path[4096];
        snprintf(path,sizeof(path),"%s.port%d.2ch.f32",dump,id);
        p->dump=fopen(path,"wb");
    }
    ++ports_opened;
    pthread_mutex_unlock(&table_lock);
    return (type<<16) | id | 0x20000000;
}
static ABI int32_t audio_close(int32_t handle) {
    pthread_mutex_lock(&table_lock);
    int32_t error=0;
    Port *p=port_of(handle,&error);
    if (p) {
        pthread_mutex_lock(&p->lock);
        p->used=0;
        p->feeder_stop=1;
        SDL_AudioStream *stream=p->stream;
        p->stream=NULL;
        int running=p->feeder_running;
        p->feeder_running=0;
        FILE *dump=p->dump;
        p->dump=NULL;
        pthread_mutex_unlock(&p->lock);
        if (running) pthread_join(p->feeder,NULL); /* the feeder is the stream's last user */
#ifdef _WIN32
        if (p->mmcss_handle && s_AvRevertMmThreadCharacteristics) {
            s_AvRevertMmThreadCharacteristics(p->mmcss_handle);
            p->mmcss_handle = NULL;
        }
#endif
        if (dump) fclose(dump);
        if (stream) SDL_DestroyAudioStream(stream);
        pthread_mutex_lock(&s_movie_lock);
        if (s_movie_port == (int)(p - ports)) {
            s_movie_active=0;
            s_movie_last_write_ns=0;
            s_movie_read=s_movie_write=s_movie_avail=0;
            s_movie_port=-1;
        }
        pthread_mutex_unlock(&s_movie_lock);
        LOG_INFO("audio", "Audio port %d closed", (int)(p - ports));
    }
    pthread_mutex_unlock(&table_lock);
    return p ? 0 : error;
}
/* `pace`: wait for this port's next period. sceAudioOutOutputs waits once for all its ports. */
static int32_t output_port(int32_t handle, const void *data, int pace) {
    int32_t error=0;
    pthread_mutex_lock(&table_lock);
    Port *p=port_of(handle,&error);
    pthread_mutex_unlock(&table_lock);
    if (!p) return error;
    pthread_mutex_lock(&p->lock);
    size_t samples=(size_t)p->frames*(size_t)p->channels;
    uint64_t period=(uint64_t)p->frames*1000000000u/48000u;
    /* Basara routes its menu/opening music through the main port (type 0) and also opens a
     * type-1 BGM port. AvPlayer's movie soundtrack is already mixed by the feeder, so leaving
     * either game path audible plays the opening song twice. Mute both while the movie owns
     * the soundtrack; the movie ring is mixed after this point and stays audible. */
    const int mute_movie_bgm=(p->type==0 || p->type==1) && movie_audio_active();
    if (data) {
        float stereo[2048 * 2];
        float peak = 0.0f;
        for (size_t f=0; f<(size_t)p->frames; ++f) {
            float ch[8] = {0.0f};
            for (int c=0; c<p->channels && c<8; ++c) {
                size_t from = f*(size_t)p->channels + (size_t)c;
                float gain = (float)p->volume[c] / (float)VOLUME_0DB;
                float val = 0.0f;
                if (p->is_float) {
                    memcpy(&val, (const char *)data + from * 4, 4);
                } else {
                    int16_t s;
                    memcpy(&s, (const char *)data + from * 2, 2);
                    val = (float)s / 32768.0f;
                }
                ch[c] = mute_movie_bgm ? 0.0f : val * gain;
            }
            float L_out = 0.0f, R_out = 0.0f;
            if (p->channels >= 8) {
                /* Downmix 8ch (7.1 surround) to 2ch Stereo:
                 * L_out = L + 0.7071*C + 0.7071*SL + 0.7071*BL
                 * R_out = R + 0.7071*C + 0.7071*SR + 0.7071*BR
                 */
                const float coef = 0.70710678f;
                L_out = ch[0] + ch[2]*coef + ch[4]*coef + ch[6]*coef;
                R_out = ch[1] + ch[2]*coef + ch[5]*coef + ch[7]*coef;
            } else if (p->channels == 2) {
                L_out = ch[0];
                R_out = ch[1];
            } else {
                /* Mono (1 ch) */
                L_out = ch[0];
                R_out = ch[0];
            }
            stereo[f * 2 + 0] = L_out;
            stereo[f * 2 + 1] = R_out;
            float abs_l = fabsf(L_out);
            float abs_r = fabsf(R_out);
            if (abs_l > peak) peak = abs_l;
            if (abs_r > peak) peak = abs_r;
        }

        size_t out_bytes = (size_t)p->frames * 2 * sizeof(float);
        if (p->dump) fwrite(stereo, 1, out_bytes, p->dump);

        p->call_count++;

        if (p->stats) {
            uint64_t now=now_ns();
            if (!p->stat_start_ns) { p->stat_start_ns=now; p->stat_min_queued=1<<30; }
            else if (now-p->stat_last_ns>p->stat_max_gap_ns) p->stat_max_gap_ns=now-p->stat_last_ns;
            p->stat_last_ns=now; ++p->stat_buffers;
            if (p->stream) {
                int queued=SDL_GetAudioStreamQueued(p->stream);
                if (queued<p->stat_min_queued) p->stat_min_queued=queued;
                if (queued==0) ++p->stat_starved;
            }
            if (now-p->stat_start_ns>=5000000000u) {
                printf("Audio stats port %d: %u buffers/5s (expected %u), max gap %.2f ms, min queued %d bytes, starved %u, underruns %u\n",
                       (int)(p-ports),p->stat_buffers,(unsigned)(5u*48000u/(unsigned)p->frames),p->stat_max_gap_ns/1e6,
                       p->stat_min_queued,p->stat_starved,p->underruns);
                p->stat_start_ns=now; p->stat_max_gap_ns=0; p->stat_starved=0; p->stat_buffers=0; p->stat_min_queued=1<<30;
            }
        }
        if (pace) {
            uint64_t now=now_ns();
            if (!p->next_deadline_ns || now>p->next_deadline_ns+8*period) p->next_deadline_ns=now; /* start or stall: restart cadence */
            else sleep_until(p->next_deadline_ns);
            p->next_deadline_ns+=period;
        }
        if (p->stream) {
            if (p->feeder_running) {
                /* Hand the period to the feeder thread; cap the queue at AUDIO_MAX_QUEUE_FRAMES
                 * (500 ms) by dropping the oldest frames (newest audio wins) so delay never
                 * accumulates. */
                size_t frames=(size_t)p->frames;
                if (p->ring_avail + frames > AUDIO_MAX_QUEUE_FRAMES) {
                    uint32_t drop = (uint32_t)(p->ring_avail + frames - AUDIO_MAX_QUEUE_FRAMES);
                    p->ring_read = (p->ring_read + drop) % AUDIO_RING_FRAMES;
                    p->ring_avail -= drop;
                }
                for (size_t i=0;i<frames;++i) {
                    uint32_t w=p->ring_write;
                    p->ring[w*2+0]=stereo[i*2+0];
                    p->ring[w*2+1]=stereo[i*2+1];
                    p->ring_write=(w+1)%AUDIO_RING_FRAMES;
                }
                p->ring_avail+=(uint32_t)frames;
            } else {
                int low=2*(int)out_bytes, queued=SDL_GetAudioStreamQueued(p->stream);
                if (queued<(int)out_bytes) {
                    static const float silence[2048*2] = {0};
                    int needed=low-queued<(int)out_bytes ? low-queued : (int)out_bytes;
                    SDL_PutAudioStreamData(p->stream,silence,needed);
                }
                SDL_PutAudioStreamData(p->stream,stereo,(int)out_bytes);
            }
        }
        ++buffers_out;
    }
    p->last_output_us=now_ns()/1000;
    pthread_mutex_unlock(&p->lock);
    return data ? (int32_t)samples : 0;
}
void runtime_audio_catchup_render(const void *data, uint32_t frames) {
    (void)data;
    (void)frames;
    /* Obsolete: Single Sink Rule enforces all guest audio outputs strictly through sceAudioOutOutput */
}
static void movie_downmix(const int16_t *s, uint32_t channels, float *out_l, float *out_r) {
    const float k = 1.0f / 32768.0f;
    const float c = 0.70710678f;
    if (channels >= 8) {
        *out_l = (s[0] + c * (s[2] + s[4] + s[6])) * k;
        *out_r = (s[1] + c * (s[2] + s[5] + s[7])) * k;
    } else if (channels >= 6) {
        *out_l = (s[0] + c * (s[2] + s[4])) * k;
        *out_r = (s[1] + c * (s[2] + s[5])) * k;
    } else if (channels == 2) {
        *out_l = s[0] * k;
        *out_r = s[1] * k;
    } else {
        *out_l = *out_r = s[0] * k;
    }
}
void runtime_audio_play_movie_pcm16(const void *pcm16, uint32_t size_bytes, uint32_t channels, uint32_t sample_rate) {
    if (!pcm16 || !size_bytes || !channels) return;
    static int s_movie_stream_logged = 0;
    if (!s_movie_stream_logged) {
        s_movie_stream_logged = 1;
        LOG_INFO("audio", "Video/Audio stream starting: %u bytes, %u ch, %u Hz", size_bytes, channels, sample_rate);
    }
    if (sample_rate == 0) sample_rate = 48000;
    const uint32_t frames = size_bytes / (channels * (uint32_t)sizeof(int16_t));
    if (!frames) return;

    const int16_t *src = (const int16_t *)pcm16;
    const uint32_t out_frames =
        sample_rate == 48000 ? frames
                             : (uint32_t)((uint64_t)frames * 48000u / sample_rate);
    if (!out_frames) return;

    /* Dedicated movie ring: never ports[0]. sceAudioOutOutput keeps writing its own ring at
     * 5.33 ms cadence (NGS2 silence/game audio); sharing it interleaved the song with silence
     * and made the opening sound chopped. The feeder adds this ring to its output instead. */
    pthread_mutex_lock(&s_movie_lock);
    s_movie_active=1;
    s_movie_last_write_ns=now_ns();
    for (uint32_t f = 0; f < out_frames; ++f) {
        const float src_f = sample_rate == 48000
                                ? (float)f
                                : ((float)f * (float)sample_rate / 48000.0f);
        uint32_t f0 = (uint32_t)src_f;
        if (f0 >= frames) f0 = frames - 1;
        const uint32_t f1 = (f0 + 1 < frames) ? (f0 + 1) : f0;
        const float frac = src_f - (float)f0;

        float l0, r0, l1, r1;
        movie_downmix(src + (size_t)f0 * channels, channels, &l0, &r0);
        movie_downmix(src + (size_t)f1 * channels, channels, &l1, &r1);
        const float l = l0 + frac * (l1 - l0);
        const float r = r0 + frac * (r1 - r0);

        const uint32_t w = s_movie_write;
        s_movie_ring[w * 2 + 0] = l;
        s_movie_ring[w * 2 + 1] = r;
        s_movie_write = (w + 1) % MOVIE_RING_FRAMES;
        if (s_movie_avail < MOVIE_RING_FRAMES) {
            ++s_movie_avail;
        } else {
            s_movie_read = (s_movie_read + 1) % MOVIE_RING_FRAMES; /* drop oldest */
        }
    }
    pthread_mutex_unlock(&s_movie_lock);
}
static ABI int32_t audio_output(int32_t handle, const void *data) { return output_port(handle,data,1); }
typedef struct { int32_t handle; const void *data; } OutputParam;
static ABI int32_t audio_outputs(const OutputParam *params, uint32_t count) {
    if (!params) return ERR_INVALID_POINTER;
    if (!count || count>PORTS) return ERR_PORT_FULL;
    int32_t result=0;
    /* One period per call for all ports (FMOD feeds main and BGM together): pacing every
       port would halve the rate and starve both. */
    for (uint32_t i=0;i<count;++i) { int32_t r=output_port(params[i].handle,params[i].data,i==0); if (r<0) return r; result=r; }
    return result;
}
static ABI int32_t audio_volume(int32_t handle, int32_t flags, const int32_t *volume) {
    int32_t error=0;
    pthread_mutex_lock(&table_lock);
    Port *p=port_of(handle,&error);
    pthread_mutex_unlock(&table_lock);
    if (!p) return error;
    if (!volume) return ERR_INVALID_POINTER;
    pthread_mutex_lock(&p->lock);
    for (int c=0;c<8;++c) if (flags & (1<<c)) {
        if (volume[c]<0 || volume[c]>VOLUME_0DB) { pthread_mutex_unlock(&p->lock); return ERR_INVALID_VOLUME; }
        p->volume[c]=volume[c];
    }
    pthread_mutex_unlock(&p->lock);
    return 0;
}
static ABI int32_t audio_state(int32_t handle, PortState *state) {
    int32_t error=0;
    pthread_mutex_lock(&table_lock);
    Port *p=port_of(handle,&error);
    pthread_mutex_unlock(&table_lock);
    if (!p) return error;
    if (!state) return ERR_INVALID_POINTER;
    memset(state,0,sizeof(*state));
    switch (p->type) {
    case 2: case 3: state->output=0x40; state->channel=1; break;          /* headphone */
    case 4: state->output=0x04; state->channel=1; state->volume=127; break; /* pad speaker */
    default: state->output=0x01; state->channel=(uint8_t)(p->channels>2 ? 2 : p->channels); break;
    }
    return 0;
}
static ABI int32_t audio_last_time(int32_t handle, uint64_t *time) {
    int32_t error=0;
    pthread_mutex_lock(&table_lock);
    Port *p=port_of(handle,&error);
    pthread_mutex_unlock(&table_lock);
    if (!p) return error;
    if (!time) return ERR_INVALID_POINTER;
    *time=p->last_output_us; return 0;
}

static const RuntimeExport exports[]={
    {"sceAudioOutInit",audio_init}, {"sceAudioOutOpen",audio_open}, {"sceAudioOutClose",audio_close},
    {"sceAudioOutOutput",audio_output}, {"sceAudioOutOutputs",audio_outputs},
    {"sceAudioOutSetVolume",audio_volume}, {"sceAudioOutGetPortState",audio_state},
    {"sceAudioOutGetLastOutputTime",audio_last_time},
};
uintptr_t runtime_audio_resolve(const char *name) { return RUNTIME_LOOKUP(exports,name); }
void runtime_audio_report(void) { printf("Runtime: audio ports opened=%zu, buffers output=%zu\n",ports_opened,buffers_out); }
