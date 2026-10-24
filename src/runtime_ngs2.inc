/* libSceNgs2 ATRAC9 / RIFF audio parser, decoder, and renderer for Sengoku Basara 4 Sumeragi */
#ifndef RUNTIME_NGS2_INC
#define RUNTIME_NGS2_INC

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <math.h>
#include <pthread.h>
#ifdef _WIN32
#include <windows.h>
#endif
#include "third_party/LibAtrac9/C/src/libatrac9.h"

#define NGS2_MAX_RACKS 64
#define NGS2_MAX_VOICES_PER_RACK 64
#define NGS2_PCM_RING_FRAMES 2048
#define NGS2_MAX_FILE_CACHE 64

struct OrbisNgs2WaveformFormat {
    uint32_t waveformType;
    uint32_t numChannels;
    uint32_t sampleRate;
    uint32_t configData;
    uint32_t frameOffset;
    uint32_t frameMargin;
};

struct OrbisNgs2WaveformBlock {
    uint32_t dataOffset;
    uint32_t dataSize;
    uint32_t numRepeats;
    uint32_t numSkipSamples;
    uint32_t numSamples;
    uint32_t reserved;
    uintptr_t userData;
};

struct OrbisNgs2WaveformInfo {
    struct OrbisNgs2WaveformFormat format;
    uint32_t dataOffset;
    uint32_t dataSize;
    uint32_t loopBeginPosition;
    uint32_t loopEndPosition;
    uint32_t numSamples;
    uint32_t audioUnitSize;
    uint32_t numAudioUnitSamples;
    uint32_t numAudioUnitPerFrame;
    uint32_t audioFrameSize;
    uint32_t numAudioFrameSamples;
    uint32_t numDelaySamples;
    uint32_t numBlocks;
    struct OrbisNgs2WaveformBlock aBlock[4];
};

struct OrbisNgs2RenderBufferInfo {
    void *buffer;
    size_t bufferSize;
    uint32_t waveformType;
    uint32_t numChannels;
};

struct OrbisNgs2VoiceParamHeader {
    uint16_t size;
    int16_t next;
    uint32_t id;
};

struct OrbisNgs2VoiceEventParam {
    struct OrbisNgs2VoiceParamHeader header;
    uint32_t eventId;
};

struct OrbisNgs2VoiceState {
    uint32_t stateFlags;
    uint64_t lastProcessTick;
    uint64_t processCount;
    uint32_t currentSamplePosition;
    uint32_t loopCount;
    uint32_t reserved;
};

typedef struct {
    uint32_t waveform_type;
    uint32_t channels;
    uint32_t sample_rate;
    uint32_t config_data;
    uint8_t atrac9_config[4];
    uint32_t superframe_size;
    uint32_t samples_per_superframe;
    uint32_t frame_samples;
    uint32_t num_frames;
    uint32_t total_samples;
    uint32_t loop_start;
    uint32_t loop_end;
    int has_loop;
    uint32_t data_offset;
    uint32_t data_size;
} Ngs2ParsedWaveform;

typedef struct {
    uintptr_t handle;
    int in_use;
    int playing;
    int paused;
    uint32_t rack_type;
    uint32_t waveform_type;

    uint32_t channels;
    uint32_t sample_rate;
    uint8_t atrac9_config[4];
    void *at9_handle;
    Atrac9CodecInfo at9_info;
    int at9_initialized;

    const uint8_t *stream_data;
    size_t stream_size;
    uint32_t sf_pos;
    uint32_t frame_pos;
    int frame_in_sf;
    uint32_t samples_decoded;
    uint32_t total_samples;

    uint32_t loop_start;
    uint32_t loop_end;
    int has_loop;
    uint32_t loop_start_offset;

    float volume;
    float pitch;

    float pcm_ring[NGS2_PCM_RING_FRAMES * 2]; // interleaved stereo float
    uint32_t pcm_write_pos;
    uint32_t pcm_read_pos;
    uint32_t pcm_avail;
} Ngs2Voice;

typedef struct {
    char path[256];
    uint64_t file_offset;
    Ngs2ParsedWaveform parsed;
    uint8_t *cached_data;
    size_t cached_data_size;
    int is_allocated;
    int used;
} Ngs2FileCacheEntry;

static Ngs2FileCacheEntry s_file_cache[NGS2_MAX_FILE_CACHE];
static Ngs2Voice s_voices[NGS2_MAX_RACKS][NGS2_MAX_VOICES_PER_RACK];
static uint32_t s_rack_types[NGS2_MAX_RACKS];
static pthread_mutex_t s_ngs2_lock = PTHREAD_MUTEX_INITIALIZER;

/* Per-voice and per-render tracing is expensive on Windows stderr (and was on by default);
 * BB_NGS2_TRACE=1 brings it back for diagnostics. Errors are still reported unconditionally. */
static int ngs2_hot_trace(void) {
    static int value = -1;
    if (value < 0) { const char *e = getenv("BB_NGS2_TRACE"); value = (e && e[0] == '1'); }
    return value;
}

static inline int is_valid_read_ptr(const void *p, size_t sz) {
    (void)sz;
    if (!p || (uintptr_t)p < 0x10000) return 0;
#ifdef _WIN32
    MEMORY_BASIC_INFORMATION mbi;
    if (VirtualQuery(p, &mbi, sizeof(mbi)) != sizeof(mbi)) return 0;
    if (mbi.State != MEM_COMMIT) return 0;
    if ((mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD)) != 0) return 0;
    return 1;
#else
    return 1;
#endif
}

static Ngs2Voice *ngs2_get_voice(uintptr_t handle) {
    uint32_t rack_idx = (handle >> 8) & 0x3f;
    uint32_t voice_idx = handle & 0x3f;
    if (rack_idx < NGS2_MAX_RACKS && voice_idx < NGS2_MAX_VOICES_PER_RACK) {
        return &s_voices[rack_idx][voice_idx];
    }
    return NULL;
}

static void ngs2_voice_decode_more(Ngs2Voice *v);

static int ngs2_parse_riff(const uint8_t *data, size_t size, Ngs2ParsedWaveform *out) {
    if (!data || size < 44) return -1;
    if (memcmp(data, "RIFF", 4) != 0 || memcmp(data + 8, "WAVE", 4) != 0) return -1;

    memset(out, 0, sizeof(*out));
    out->waveform_type = 2; // ATRAC9
    out->channels = 2;
    out->sample_rate = 48000;
    out->frame_samples = 256;
    out->superframe_size = 384;
    out->samples_per_superframe = 1024;

    size_t pos = 12;
    int found_fmt = 0, found_data = 0;
    while (pos + 8 <= size) {
        const char *cid = (const char *)(data + pos);
        uint32_t csz = *(const uint32_t *)(data + pos + 4);
        const uint8_t *cdata = data + pos + 8;
        if (pos + 8 + csz > size) {
            if (memcmp(cid, "data", 4) == 0) {
                found_data = 1;
                out->data_offset = (uint32_t)(pos + 8);
                out->data_size = (uint32_t)(size - (pos + 8));
            }
            break;
        }

        if (memcmp(cid, "fmt ", 4) == 0 && csz >= 16) {
            found_fmt = 1;
            uint16_t tag = *(const uint16_t *)(cdata + 0);
            out->channels = *(const uint16_t *)(cdata + 2);
            out->sample_rate = *(const uint32_t *)(cdata + 4);
            out->superframe_size = *(const uint16_t *)(cdata + 12);
            if (tag == 0xFFFE && csz >= 48) {
                memcpy(out->atrac9_config, cdata + 44, 4);
                out->config_data = *(const uint32_t *)out->atrac9_config;
            }
        } else if (memcmp(cid, "fact", 4) == 0 && csz >= 4) {
            out->total_samples = *(const uint32_t *)(cdata + 0);
        } else if (memcmp(cid, "smpl", 4) == 0 && csz >= 36) {
            uint32_t num_loops = *(const uint32_t *)(cdata + 28);
            if (num_loops > 0 && csz >= 60) {
                out->has_loop = 1;
                out->loop_start = *(const uint32_t *)(cdata + 36 + 8);
                out->loop_end = *(const uint32_t *)(cdata + 36 + 12);
            }
        } else if (memcmp(cid, "data", 4) == 0) {
            found_data = 1;
            out->data_offset = (uint32_t)(pos + 8);
            out->data_size = csz;
        }
        pos += 8 + ((csz + 1) & ~1u);
    }

    if (!found_fmt || !found_data) return -1;

    // Use libatrac9 to get exact codec params if configData present
    if (out->config_data != 0) {
        void *th = Atrac9GetHandle();
        if (th) {
            if (Atrac9InitDecoder(th, out->atrac9_config) == 0) {
                Atrac9CodecInfo ci;
                Atrac9GetCodecInfo(th, &ci);
                if (ci.channels > 0) out->channels = ci.channels;
                if (ci.samplingRate > 0) out->sample_rate = ci.samplingRate;
                if (ci.superframeSize > 0) out->superframe_size = ci.superframeSize;
                if (ci.frameSamples > 0) out->frame_samples = ci.frameSamples;
                if (ci.framesInSuperframe > 0) out->num_frames = ci.framesInSuperframe;
                out->samples_per_superframe = out->frame_samples * (out->num_frames ? out->num_frames : 1);
            }
            Atrac9ReleaseHandle(th);
        }
    }

    if (out->total_samples == 0 && out->superframe_size > 0 && out->samples_per_superframe > 0) {
        out->total_samples = (out->data_size / out->superframe_size) * out->samples_per_superframe;
    }
    return 0;
}

static void ngs2_fill_waveform_info(const Ngs2ParsedWaveform *parsed, struct OrbisNgs2WaveformInfo *info) {
    if (!info) return;
    memset(info, 0, sizeof(*info));
    info->format.waveformType = parsed->waveform_type ? parsed->waveform_type : 2;
    info->format.numChannels = parsed->channels ? parsed->channels : 2;
    info->format.sampleRate = parsed->sample_rate ? parsed->sample_rate : 48000;
    info->format.configData = parsed->config_data;
    info->format.frameOffset = 0;
    info->format.frameMargin = 0;

    info->dataOffset = parsed->data_offset;
    info->dataSize = parsed->data_size;
    info->loopBeginPosition = parsed->loop_start;
    info->loopEndPosition = parsed->loop_end ? parsed->loop_end : parsed->total_samples;
    info->numSamples = parsed->total_samples;

    info->audioUnitSize = parsed->superframe_size ? parsed->superframe_size : 384;
    info->numAudioUnitSamples = parsed->samples_per_superframe ? parsed->samples_per_superframe : 1024;
    info->numAudioUnitPerFrame = 1;
    info->audioFrameSize = parsed->superframe_size / (parsed->num_frames ? parsed->num_frames : 1);
    info->numAudioFrameSamples = parsed->frame_samples ? parsed->frame_samples : 256;
    info->numDelaySamples = 0;

    info->numBlocks = 1;
    info->aBlock[0].dataOffset = parsed->data_offset;
    info->aBlock[0].dataSize = parsed->data_size;
    info->aBlock[0].numRepeats = 0;
    info->aBlock[0].numSkipSamples = 0;
    info->aBlock[0].numSamples = parsed->total_samples;
    info->aBlock[0].userData = 0;
}

static ABI int32_t ngs2_sys_create(const void *opt, const void *alloc, uintptr_t *out) {
    (void)opt; (void)alloc;
    if (out) *out = (uintptr_t)new_id();
    if (ngs2_hot_trace()) {
        fprintf(stderr, "[NGS2] sceNgs2SystemCreateWithAllocator() -> handle=0x%llx\n",
                out ? (unsigned long long)*out : 0);
        fflush(stderr);
    }
    return 0;
}

static ABI int32_t ngs2_rack_create(uintptr_t sys, uint32_t id, const void *opt, const void *alloc, uintptr_t *out) {
    (void)sys; (void)opt; (void)alloc;
    static uint32_t s_next_rack = 1;
    pthread_mutex_lock(&s_ngs2_lock);
    uint32_t r_id = (s_next_rack++) % NGS2_MAX_RACKS;
    if (r_id == 0) r_id = (s_next_rack++) % NGS2_MAX_RACKS;
    s_rack_types[r_id] = id;
    pthread_mutex_unlock(&s_ngs2_lock);
    if (out) *out = (uintptr_t)r_id;
    if (ngs2_hot_trace()) {
        fprintf(stderr, "[NGS2] sceNgs2RackCreateWithAllocator(sys=0x%llx, id=%u) -> handle=0x%llx\n",
                (unsigned long long)sys, id, out ? (unsigned long long)*out : 0);
        fflush(stderr);
    }
    return 0;
}

static ABI int32_t ngs2_rack_destroy(uintptr_t rack) {
    uint32_t r_id = (uint32_t)rack & 0x7f;
    pthread_mutex_lock(&s_ngs2_lock);
    if (r_id < NGS2_MAX_RACKS) {
        for (int v = 0; v < NGS2_MAX_VOICES_PER_RACK; ++v) {
            s_voices[r_id][v].in_use = 0;
            s_voices[r_id][v].playing = 0;
            s_voices[r_id][v].paused = 0;
            s_voices[r_id][v].pcm_avail = 0;
            s_voices[r_id][v].stream_data = NULL;
            s_voices[r_id][v].stream_size = 0;
        }
        s_rack_types[r_id] = 0;
    }
    pthread_mutex_unlock(&s_ngs2_lock);
    if (ngs2_hot_trace()) {
        fprintf(stderr, "[NGS2] sceNgs2RackDestroy(rack=0x%llx)\n", (unsigned long long)rack);
        fflush(stderr);
    }
    return 0;
}

static ABI int32_t ngs2_rack_control(uintptr_t rack, const void *param_list) {
    if (!param_list) return 0;
    uint32_t r_id = (uint32_t)rack & 0x7f;
    if (r_id >= NGS2_MAX_RACKS) return 0;

    pthread_mutex_lock(&s_ngs2_lock);
    const uint8_t *cur = (const uint8_t *)param_list;
    int depth = 0;
    while (cur && depth < 32) {
        if (!is_valid_read_ptr(cur, sizeof(struct OrbisNgs2VoiceParamHeader))) break;
        const struct OrbisNgs2VoiceParamHeader *h = (const struct OrbisNgs2VoiceParamHeader *)cur;
        if (h->size < 8) break;

        uint32_t id = h->id;
        // Event (Play = 0, Stop = 1, Pause = 2, Resume = 3) applied to rack
        if (id == 0x00000006 && h->size >= 12) {
            const struct OrbisNgs2VoiceEventParam *p = (const struct OrbisNgs2VoiceEventParam *)cur;
            for (int v = 0; v < NGS2_MAX_VOICES_PER_RACK; ++v) {
                Ngs2Voice *voice = &s_voices[r_id][v];
                if (!voice->in_use) continue;
                if (p->eventId == 0) {
                    voice->playing = 1;
                    voice->paused = 0;
                    ngs2_voice_decode_more(voice);
                } else if (p->eventId == 1) {
                    voice->playing = 0;
                    voice->paused = 0;
                    voice->pcm_avail = 0;
                } else if (p->eventId == 2) {
                    voice->paused = 1;
                } else if (p->eventId == 3) {
                    voice->paused = 0;
                    voice->playing = 1;
                }
            }
        }
        if (h->next <= 0 || h->next > 4096) break;
        cur += h->next;
        depth++;
    }
    pthread_mutex_unlock(&s_ngs2_lock);
    return 0;
}

static ABI int32_t ngs2_voice_handle(uintptr_t rack, uint32_t idx, uintptr_t *out) {
    uint32_t r = (uint32_t)rack & 0x3f;
    uint32_t v = idx & 0x3f;
    if (out) *out = (uintptr_t)(0x100000 | (r << 8) | v);
    if (ngs2_hot_trace()) {
        fprintf(stderr, "[NGS2] sceNgs2RackGetVoiceHandle(rack=0x%llx, idx=%u) -> handle=0x%llx\n",
                (unsigned long long)rack, idx, out ? (unsigned long long)*out : 0);
        fflush(stderr);
    }
    return 0;
}

static ABI int32_t ngs2_voice_state(uintptr_t voice, void *state, uint64_t size) {
    if (state && size >= sizeof(uint32_t)) {
        memset(state, 0, (size_t)size);
        Ngs2Voice *v = ngs2_get_voice(voice);
        struct OrbisNgs2VoiceState *st = (struct OrbisNgs2VoiceState *)state;
        st->stateFlags = (v && v->playing) ? 1 : 0;
        st->currentSamplePosition = (v) ? v->samples_decoded : 0;
        st->loopCount = 0;
    }
    return 0;
}

static ABI int32_t ngs2_voice_flags(uintptr_t voice, uint32_t *flags) {
    if (flags) {
        Ngs2Voice *v = ngs2_get_voice(voice);
        *flags = (v && v->playing) ? 1 : 0;
    }
    return 0;
}

static ABI int32_t ngs2_parse_data(const void *data, uint64_t size, void *info) {
    if (!data || size < 44 || !info) {
        if (info) memset(info, 0, sizeof(struct OrbisNgs2WaveformInfo));
        return 0;
    }

    Ngs2ParsedWaveform parsed;
    if (ngs2_parse_riff((const uint8_t *)data, (size_t)size, &parsed) == 0) {
        ngs2_fill_waveform_info(&parsed, (struct OrbisNgs2WaveformInfo *)info);
        static uint32_t s_parsed_data_count = 0;
        s_parsed_data_count++;
        if (ngs2_hot_trace() && (s_parsed_data_count <= 5 || s_parsed_data_count % 100 == 0)) {
            fprintf(stderr, "[NGS2] sceNgs2ParseWaveformData (#%u): ch=%u rate=%u total=%u loop=(%u..%u) dataOff=%u dataSz=%u\n",
                    s_parsed_data_count, parsed.channels, parsed.sample_rate, parsed.total_samples,
                    parsed.loop_start, parsed.loop_end, parsed.data_offset, parsed.data_size);
            fflush(stderr);
        }
    } else {
        memset(info, 0, sizeof(struct OrbisNgs2WaveformInfo));
    }
    return 0;
}

static ABI int32_t ngs2_parse_file(const char *path, uint64_t offset, void *info) {
    if (!path || !info) return 0;

    /* Cache lookups take the render lock only for the lookup; the file read happens outside it.
     * Reading a multi-megabyte waveform under the lock stalled sceNgs2SystemRender (audio gaps
     * of 100-200 ms) whenever a stage loaded a sound. */
    pthread_mutex_lock(&s_ngs2_lock);
    for (int i = 0; i < NGS2_MAX_FILE_CACHE; ++i) {
        Ngs2FileCacheEntry *e = &s_file_cache[i];
        if (e->used && e->file_offset == offset && strcmp(e->path, path) == 0) {
            ngs2_fill_waveform_info(&e->parsed, (struct OrbisNgs2WaveformInfo *)info);
            pthread_mutex_unlock(&s_ngs2_lock);
            return 0;
        }
    }
    pthread_mutex_unlock(&s_ngs2_lock);

    Ngs2ParsedWaveform parsed;
    memset(&parsed, 0, sizeof(parsed));
    uint8_t *cached = NULL;
    size_t cached_size = 0;
    int parsed_ok = 0;

    int fd = (int)runtime_file_open(path, 0, 0);
    if (fd >= 0) {
        uint8_t hdr[2048];
        int64_t n = runtime_file_pread(fd, hdr, sizeof(hdr), (int64_t)offset);
        if (n >= 44 && ngs2_parse_riff(hdr, (size_t)n, &parsed) == 0) {
            parsed_ok = 1;
            if (parsed.data_size > 0 && parsed.data_size < 64 * 1024 * 1024) {
                cached = malloc(parsed.data_size);
                if (cached) {
                    int64_t read_bytes = runtime_file_pread(fd, cached, parsed.data_size,
                                                            (int64_t)(offset + parsed.data_offset));
                    cached_size = read_bytes > 0 ? (size_t)read_bytes : 0;
                }
            }
        }
        runtime_file_close(fd);
    }

    pthread_mutex_lock(&s_ngs2_lock);
    Ngs2FileCacheEntry *entry = NULL;
    for (int i = 0; i < NGS2_MAX_FILE_CACHE; ++i) {
        if (s_file_cache[i].used && s_file_cache[i].file_offset == offset &&
            strcmp(s_file_cache[i].path, path) == 0) {
            entry = &s_file_cache[i]; /* another thread cached it meanwhile */
            break;
        }
    }
    if (!entry && parsed_ok) {
        for (int i = 0; i < NGS2_MAX_FILE_CACHE; ++i) {
            if (!s_file_cache[i].used) { entry = &s_file_cache[i]; break; }
        }
        if (!entry) { entry = &s_file_cache[0]; }
        if (entry->is_allocated && entry->cached_data) free(entry->cached_data);
        memset(entry, 0, sizeof(*entry));
        strncpy(entry->path, path, sizeof(entry->path) - 1);
        entry->file_offset = offset;
        entry->parsed = parsed;
        entry->cached_data = cached;
        entry->cached_data_size = cached_size;
        entry->is_allocated = 1;
        entry->used = 1;
        cached = NULL; /* now owned by the cache */
    }

    if (entry && entry->used) {
        ngs2_fill_waveform_info(&entry->parsed, (struct OrbisNgs2WaveformInfo *)info);
        if (ngs2_hot_trace()) {
            fprintf(stderr, "[NGS2] sceNgs2ParseWaveformFile('%s', off=%llu): ch=%u rate=%u total=%u loop=(%u..%u) preloaded=%llu\n",
                    path, (unsigned long long)offset, entry->parsed.channels, entry->parsed.sample_rate,
                    entry->parsed.total_samples, entry->parsed.loop_start, entry->parsed.loop_end,
                    (unsigned long long)entry->cached_data_size);
            fflush(stderr);
        }
    } else {
        memset(info, 0, sizeof(struct OrbisNgs2WaveformInfo));
    }
    pthread_mutex_unlock(&s_ngs2_lock);
    free(cached);
    return 0;
}

static ABI int32_t ngs2_calc_block(const void *info_or_fmt, uint64_t pos, uint64_t count, void *out_ptr) {
    if (!out_ptr) return 0;
    struct OrbisNgs2WaveformBlock *b = (struct OrbisNgs2WaveformBlock *)out_ptr;
    memset(b, 0, sizeof(*b));

    const struct OrbisNgs2WaveformFormat *fmt = (const struct OrbisNgs2WaveformFormat *)info_or_fmt;
    uint32_t superframe_size = 384;
    uint32_t samples_per_sf = 1024;

    if (fmt && fmt->configData) {
        void *th = Atrac9GetHandle();
        if (th) {
            if (Atrac9InitDecoder(th, (unsigned char *)&fmt->configData) == 0) {
                Atrac9CodecInfo ci;
                Atrac9GetCodecInfo(th, &ci);
                if (ci.superframeSize > 0) superframe_size = ci.superframeSize;
                if (ci.framesInSuperframe > 0 && ci.frameSamples > 0)
                    samples_per_sf = ci.framesInSuperframe * ci.frameSamples;
            }
            Atrac9ReleaseHandle(th);
        }
    }

    uint32_t sf_index = (uint32_t)(pos / samples_per_sf);
    uint32_t skip = (uint32_t)(pos % samples_per_sf);
    uint32_t needed_sf = (uint32_t)((count + skip + samples_per_sf - 1) / samples_per_sf);

    b->dataOffset = sf_index * superframe_size;
    b->dataSize = needed_sf * superframe_size;
    b->numSkipSamples = skip;
    b->numSamples = (uint32_t)count;
    b->numRepeats = 0;
    b->userData = 0;
    return 0;
}

static void ngs2_voice_decode_more(Ngs2Voice *v) {
    if (!v->playing || !v->stream_data || !v->stream_size) return;

    int decode_as_pcm = (v->waveform_type != 2) || (!v->at9_initialized);

    if (!decode_as_pcm && v->at9_initialized) {
        short pcm16[256 * 8];
        int sf_size = v->at9_info.superframeSize > 0 ? v->at9_info.superframeSize : 384;
        int frames_in_sf = v->at9_info.framesInSuperframe > 0 ? v->at9_info.framesInSuperframe : 4;
        int frame_samples = v->at9_info.frameSamples > 0 ? v->at9_info.frameSamples : 256;
        int channels = v->at9_info.channels > 0 ? v->at9_info.channels : 2;

        while (v->pcm_avail + frame_samples <= NGS2_PCM_RING_FRAMES && v->sf_pos < v->stream_size) {
            size_t cur_offset = v->sf_pos + v->frame_pos;
            if (cur_offset >= v->stream_size) {
                v->sf_pos = (uint32_t)v->stream_size;
                break;
            }

            int used = 0;
            int err = Atrac9Decode(v->at9_handle, v->stream_data + cur_offset, pcm16, &used);
            if (err != 0 || used <= 0) {
                // If decode fails at the very start, this stream is likely raw PCM16 SFX!
                if (v->sf_pos == 0 && v->samples_decoded == 0) {
                    decode_as_pcm = 1;
                    v->at9_initialized = 0;
                    break;
                }
                v->sf_pos += sf_size;
                v->frame_pos = 0;
                v->frame_in_sf = 0;
                if (v->sf_pos >= v->stream_size) {
                    break;
                }
                continue;
            }

            v->frame_pos += used;
            v->frame_in_sf++;
            if (v->frame_in_sf >= frames_in_sf || v->frame_pos >= (uint32_t)sf_size) {
                v->sf_pos += sf_size;
                v->frame_pos = 0;
                v->frame_in_sf = 0;
            }

            float frame_peak = 0.0f;
            for (int i = 0; i < frame_samples; ++i) {
                uint32_t wpos = (v->pcm_write_pos + i) % NGS2_PCM_RING_FRAMES;
                float l = 0.0f, r = 0.0f;
                if (channels >= 2) {
                    l = (float)pcm16[i * channels + 0] / 32768.0f;
                    r = (float)pcm16[i * channels + 1] / 32768.0f;
                } else {
                    l = r = (float)pcm16[i] / 32768.0f;
                }
                v->pcm_ring[wpos * 2 + 0] = l;
                v->pcm_ring[wpos * 2 + 1] = r;
                float al = fabsf(l), ar = fabsf(r);
                if (al > frame_peak) frame_peak = al;
                if (ar > frame_peak) frame_peak = ar;
            }

            v->pcm_write_pos = (v->pcm_write_pos + frame_samples) % NGS2_PCM_RING_FRAMES;
            v->pcm_avail += frame_samples;
            v->samples_decoded += frame_samples;

            if (ngs2_hot_trace() && frame_peak > 0.0005f) {
                static uint32_t s_sound_frames = 0;
                if (s_sound_frames++ < 30 || s_sound_frames % 50 == 0) {
                    fprintf(stderr, "[NGS2] Voice 0x%llx decoded frame peak=%.4f (avail=%u sf_pos=%u)\n",
                            (unsigned long long)v->handle, frame_peak, v->pcm_avail, v->sf_pos);
                    fflush(stderr);
                }
            }

            // Loop handling
            if (v->has_loop && v->loop_end > v->loop_start && v->samples_decoded >= v->loop_end) {
                uint32_t loop_offset = v->loop_start_offset;
                if (sf_size > 0) loop_offset = (loop_offset / sf_size) * sf_size;
                if (loop_offset >= v->stream_size) loop_offset = 0;
                v->sf_pos = loop_offset;
                v->frame_pos = 0;
                v->frame_in_sf = 0;
                v->samples_decoded = v->loop_start;
                Atrac9InitDecoder(v->at9_handle, v->atrac9_config);
            }
        }

        if (!decode_as_pcm) {
            if (v->sf_pos >= v->stream_size) {
                if (v->has_loop && v->loop_end > v->loop_start) {
                    uint32_t loop_offset = v->loop_start_offset;
                    if (sf_size > 0) loop_offset = (loop_offset / sf_size) * sf_size;
                    if (loop_offset >= v->stream_size) loop_offset = 0;
                    v->sf_pos = loop_offset;
                    v->frame_pos = 0;
                    v->frame_in_sf = 0;
                    v->samples_decoded = v->loop_start;
                    Atrac9InitDecoder(v->at9_handle, v->atrac9_config);
                } else if (v->pcm_avail == 0) {
                    v->playing = 0;
                }
            }
            return;
        }
    }

    if (decode_as_pcm) {
        // Raw PCM16 streaming (for footsteps and short non-ATRAC9 SFX)
        int channels = v->channels ? v->channels : 2;
        const int16_t *pcm16 = (const int16_t *)v->stream_data;
        size_t total_pcm_frames = v->stream_size / (channels * sizeof(int16_t));

        while (v->pcm_avail + 256 <= NGS2_PCM_RING_FRAMES && v->frame_pos < total_pcm_frames) {
            uint32_t chunk = (total_pcm_frames - v->frame_pos) < 256 ? (uint32_t)(total_pcm_frames - v->frame_pos) : 256;
            float frame_peak = 0.0f;
            for (uint32_t i = 0; i < chunk; ++i) {
                uint32_t wpos = (v->pcm_write_pos + i) % NGS2_PCM_RING_FRAMES;
                size_t src_idx = (v->frame_pos + i) * channels;
                float l = 0.0f, r = 0.0f;
                if (channels >= 2) {
                    l = (float)pcm16[src_idx + 0] / 32768.0f;
                    r = (float)pcm16[src_idx + 1] / 32768.0f;
                } else {
                    l = r = (float)pcm16[src_idx] / 32768.0f;
                }
                v->pcm_ring[wpos * 2 + 0] = l;
                v->pcm_ring[wpos * 2 + 1] = r;
                float al = fabsf(l), ar = fabsf(r);
                if (al > frame_peak) frame_peak = al;
                if (ar > frame_peak) frame_peak = ar;
            }
            v->pcm_write_pos = (v->pcm_write_pos + chunk) % NGS2_PCM_RING_FRAMES;
            v->pcm_avail += chunk;
            v->frame_pos += chunk;
            v->samples_decoded += chunk;

            if (ngs2_hot_trace() && frame_peak > 0.0005f) {
                static uint32_t s_pcm_sound_frames = 0;
                if (s_pcm_sound_frames++ < 30 || s_pcm_sound_frames % 50 == 0) {
                    fprintf(stderr, "[NGS2] Voice 0x%llx (PCM16) frame peak=%.4f (avail=%u pos=%u/%zu)\n",
                            (unsigned long long)v->handle, frame_peak, v->pcm_avail, v->frame_pos, total_pcm_frames);
                    fflush(stderr);
                }
            }

            if (v->has_loop && v->loop_end > v->loop_start && v->samples_decoded >= v->loop_end) {
                v->frame_pos = v->loop_start < total_pcm_frames ? v->loop_start : 0;
                v->samples_decoded = v->loop_start;
            }
        }
        if (v->frame_pos >= total_pcm_frames) {
            if (v->has_loop && v->loop_end > v->loop_start) {
                v->frame_pos = v->loop_start < total_pcm_frames ? v->loop_start : 0;
                v->samples_decoded = v->loop_start;
            } else if (v->pcm_avail == 0) {
                v->playing = 0;
            }
        }
    }
}

static ABI int32_t ngs2_voice_control(uintptr_t voice, const void *param_list) {
    if (!param_list) return 0;
    pthread_mutex_lock(&s_ngs2_lock);

    Ngs2Voice *v = ngs2_get_voice(voice);
    static uint32_t s_vc_total = 0;
    s_vc_total++;

    uint32_t first_id = 0;
    if (is_valid_read_ptr(param_list, 8)) {
        first_id = *(const uint32_t*)((const uint8_t*)param_list + 4);
    }
    int is_noisy = (first_id == 0x05 || first_id == 0x01 || first_id == 0x20000004 || first_id == 0x20010004 || first_id == 0x30000005);
    int should_log = ngs2_hot_trace() && (!is_noisy || s_vc_total <= 10);
    if (should_log) {
        fprintf(stderr, "[NGS2] VoiceControl voice=0x%llx v=%p (call=%u)\n",
                (unsigned long long)voice, (void*)v, s_vc_total);
        fflush(stderr);
    }

    if (!v) {
        pthread_mutex_unlock(&s_ngs2_lock);
        return 0;
    }

    v->handle = voice;
    v->in_use = 1;
    uint32_t rack_id = (voice >> 8) & 0x7f;
    v->rack_type = rack_id < NGS2_MAX_RACKS ? s_rack_types[rack_id] : 0;
    if (v->volume <= 0.0001f) v->volume = 1.0f;
    if (v->pitch <= 0.0001f) v->pitch = 1.0f;

    const uint8_t *cur = (const uint8_t *)param_list;
    int depth = 0;
    while (cur && depth < 32) {
        if (!is_valid_read_ptr(cur, sizeof(struct OrbisNgs2VoiceParamHeader))) break;

        const struct OrbisNgs2VoiceParamHeader *h = (const struct OrbisNgs2VoiceParamHeader *)cur;
        if (h->size < 8) break;

        uint32_t id = h->id;

        if (should_log) {
            const uint8_t *raw = cur;
            fprintf(stderr, "  param[%d]: id=0x%08x sz=%u nxt=%d | %02x%02x%02x%02x %02x%02x%02x%02x\n",
                    depth, id, h->size, h->next,
                    raw[0], raw[1], raw[2], raw[3], raw[4], raw[5], raw[6], raw[7]);
            fflush(stderr);
        }

        // 1. Setup / Format (Sampler racks: 0x10000000, 0x20000000, 0x20010000, etc.)
        if ((id == 0x10000000 || id == 0x20000000 || id == 0x20010000) && h->size >= 32) {
            const struct OrbisNgs2WaveformFormat *fmt = (const struct OrbisNgs2WaveformFormat *)(cur + 8);
            v->waveform_type = fmt->waveformType;
            v->channels = fmt->numChannels ? fmt->numChannels : 2;
            v->sample_rate = fmt->sampleRate ? fmt->sampleRate : 48000;
            memcpy(v->atrac9_config, &fmt->configData, 4);

            if (ngs2_hot_trace()) {
                fprintf(stderr, "[NGS2] Voice Setup 0x%llx: type=%u ch=%u rate=%u cfg=%08x\n",
                        (unsigned long long)voice, fmt->waveformType, v->channels, v->sample_rate, fmt->configData);
                fflush(stderr);
            }

            if (fmt->waveformType == 2 || fmt->configData != 0) {
                if (!v->at9_handle) v->at9_handle = Atrac9GetHandle();
                if (v->at9_handle && Atrac9InitDecoder(v->at9_handle, v->atrac9_config) == 0) {
                    v->at9_initialized = 1;
                    Atrac9GetCodecInfo(v->at9_handle, &v->at9_info);
                    fprintf(stderr, "  ATRAC9 initialized: sfSize=%u framesInSf=%d smpPerFrame=%d\n",
                            v->at9_info.superframeSize, v->at9_info.framesInSuperframe, v->at9_info.frameSamples);
                    fflush(stderr);
                }
            } else {
                v->at9_initialized = 0;
            }
        }
        // 2. WaveformBlocks (Sampler racks: 0x10000001, 0x20000001, 0x20010001)
        else if ((id == 0x10000001 || id == 0x20000001 || id == 0x20010001) && h->size >= 24) {
            const void *data = *(const void *const *)(cur + 8);
            uint32_t num_blocks = 0;
            const struct OrbisNgs2WaveformBlock *b = NULL;
            if (h->size >= 32) {
                num_blocks = *(const uint32_t *)(cur + 20);
                const void *ab_ptr = *(const void *const *)(cur + 24);
                if (num_blocks > 0 && is_valid_read_ptr(ab_ptr, sizeof(struct OrbisNgs2WaveformBlock))) {
                    b = (const struct OrbisNgs2WaveformBlock *)ab_ptr;
                }
            }

            // If data pointer is null/invalid, search across block userDatas
            if (!is_valid_read_ptr(data, 16) && b && num_blocks > 0) {
                for (uint32_t bi = 0; bi < num_blocks; ++bi) {
                    if (is_valid_read_ptr(&b[bi], sizeof(struct OrbisNgs2WaveformBlock)) &&
                        is_valid_read_ptr((const void*)b[bi].userData, 16)) {
                        data = (const void*)b[bi].userData;
                        break;
                    }
                }
            }

            uint32_t data_off = 0;
            uint32_t data_sz = 0;
            uint32_t num_samples = 0;
            int any_loop = 0;

            if (b && num_blocks > 0) {
                uint32_t min_off = b[0].dataOffset;
                uint32_t max_end = b[0].dataOffset + b[0].dataSize;
                num_samples = b[0].numSamples;
                if (b[0].numRepeats != 0) any_loop = 1;

                // Iterate all sequential blocks (block[0 .. numBlocks-1])
                for (uint32_t bi = 1; bi < num_blocks; ++bi) {
                    if (is_valid_read_ptr(&b[bi], sizeof(struct OrbisNgs2WaveformBlock))) {
                        if (b[bi].dataOffset < min_off) min_off = b[bi].dataOffset;
                        if (b[bi].dataOffset + b[bi].dataSize > max_end) max_end = b[bi].dataOffset + b[bi].dataSize;
                        num_samples += b[bi].numSamples;
                        if (b[bi].numRepeats != 0) any_loop = 1;
                    }
                }
                data_off = min_off;
                data_sz = (max_end > min_off) ? (max_end - min_off) : 0;
            }

            if (ngs2_hot_trace()) {
                fprintf(stderr, "[NGS2] WaveformBlocks 0x%llx: data=%p numBlocks=%u aBlock=%p off=%u sz=%u smp=%u anyLoop=%d\n",
                        (unsigned long long)voice, data, num_blocks, (const void*)b, data_off, data_sz, num_samples, any_loop);
                fflush(stderr);
            }

            if (num_blocks == 0 && !is_valid_read_ptr(data, 16)) {
                // Not a new waveform assignment; preserve existing stream
            } else if (is_valid_read_ptr(data, 16)) {
                int has_loop = 0;
                uint32_t loop_start = 0, loop_end = 0, loop_start_offset = 0;
                if (memcmp(data, "RIFF", 4) == 0) {
                    Ngs2ParsedWaveform pw;
                    if (ngs2_parse_riff((const uint8_t *)data, 65536, &pw) == 0) {
                        if (data_off == 0) data_off = pw.data_offset;
                        if (data_sz == 0) data_sz = pw.data_size;
                        memcpy(v->atrac9_config, pw.atrac9_config, 4);
                        has_loop = pw.has_loop;
                        loop_start = pw.loop_start;
                        loop_end = pw.loop_end;
                        if (pw.samples_per_superframe > 0 && pw.superframe_size > 0) {
                            loop_start_offset = (pw.loop_start / pw.samples_per_superframe) * pw.superframe_size;
                        }
                    }
                }

                // If block explicitly specifies numRepeats == 0 across blocks, it is ONE-SHOT (e.g. footsteps)
                if (num_blocks > 0 && !any_loop) {
                    has_loop = 0;
                }
                v->has_loop = has_loop;
                v->loop_start = loop_start;
                v->loop_end = loop_end;
                v->loop_start_offset = loop_start_offset;

                // Re-trigger clean state: always reset ATRAC9 decoder and clear sample positions
                if (!v->at9_handle) v->at9_handle = Atrac9GetHandle();
                if (v->at9_handle && (v->atrac9_config[0] != 0 || v->atrac9_config[1] != 0)) {
                    if (Atrac9InitDecoder(v->at9_handle, v->atrac9_config) == 0) {
                        v->at9_initialized = 1;
                        Atrac9GetCodecInfo(v->at9_handle, &v->at9_info);
                    } else {
                        v->at9_initialized = 0;
                    }
                } else {
                    v->at9_initialized = 0;
                }

                v->stream_data = (const uint8_t *)data + data_off;
                v->stream_size = data_sz;
                v->sf_pos = 0;
                v->frame_pos = 0;
                v->frame_in_sf = 0;
                v->pcm_write_pos = 0;
                v->pcm_read_pos = 0;
                v->pcm_avail = 0;
                v->samples_decoded = 0;
                if (ngs2_hot_trace()) {
                    fprintf(stderr, "  assigned stream_data=%p stream_size=%zu has_loop=%d at9_init=%d\n",
                            v->stream_data, v->stream_size, v->has_loop, v->at9_initialized);
                    fflush(stderr);
                }
            }
        }
        // 3. Matrix levels (id == 0x00000001 or (id & 0xffff) == 0x0004: e.g. 0x20000004, 0x20010004)
        else if ((id == 0x00000001 || (id & 0xffff) == 0x0004) && h->size >= 12) {
            const float *floats = (const float *)(cur + 8);
            uint32_t num_f = (h->size - 8) / 4;
            float max_g = 0.0f;
            for (uint32_t fi = 0; fi < num_f; ++fi) {
                float g = fabsf(floats[fi]);
                if (g > max_g && g <= 10.0f) max_g = g;
            }
            if (max_g > 0.0001f) {
                v->volume = max_g;
            }
            if (ngs2_hot_trace()) {
                fprintf(stderr, "[NGS2] VoiceMatrixLevels 0x%llx: id=0x%08x max_g=%.4f (vol=%.4f)\n",
                        (unsigned long long)voice, id, max_g, v->volume);
                fflush(stderr);
            }
        }
        // 4. Port Volume (id == 0x00000003) - OrbisNgs2VoicePortVolumeParam
        else if (id == 0x00000003 && h->size >= 16) {
            uint32_t port = *(const uint32_t *)(cur + 8);
            float vol = *(const float *)(cur + 12);
            if (vol > 0.0f && vol <= 10.0f) {
                v->volume = vol;
            }
            static uint32_t s_pvol_cnt = 0;
            if (ngs2_hot_trace() && s_pvol_cnt++ < 30) {
                fprintf(stderr, "[NGS2] VoicePortVolume 0x%llx: port=%u level=%.4f (voice vol=%.4f)\n",
                        (unsigned long long)voice, port, vol, v->volume);
                fflush(stderr);
            }
        }
        // 5. Volume (id == 0x00000005) - OrbisNgs2VoiceVolumeParam
        else if (id == 0x00000005 && h->size >= 12) {
            float vol = *(const float *)(cur + 8);
            if (vol > 0.0f && vol <= 10.0f) {
                v->volume = vol;
            }
            if (ngs2_hot_trace()) {
                fprintf(stderr, "[NGS2] VoiceVolume 0x%llx: vol=%.4f\n", (unsigned long long)voice, vol);
                fflush(stderr);
            }
        }
        // 6. Event (Play = 0, Stop = 1, Pause = 2, Resume = 3, KeyOff = 4)
        else if (id == 0x00000006 && h->size >= 12) {
            const struct OrbisNgs2VoiceEventParam *p = (const struct OrbisNgs2VoiceEventParam *)cur;
            if (ngs2_hot_trace()) {
                fprintf(stderr, "[NGS2] VoiceEvent 0x%llx: eventId=%u\n", (unsigned long long)voice, p->eventId);
                fflush(stderr);
            }
            if (p->eventId == 0) { // Play
                v->playing = 1;
                v->paused = 0;
                ngs2_voice_decode_more(v);
                if (ngs2_hot_trace()) {
                    fprintf(stderr, "  started playing: avail=%u sf_pos=%u stream_size=%zu vol=%.4f\n",
                            v->pcm_avail, v->sf_pos, v->stream_size, v->volume);
                    fflush(stderr);
                }
            } else if (p->eventId == 1) { // Stop
                v->playing = 0;
                v->paused = 0;
                v->pcm_avail = 0;
                v->sf_pos = 0;
                v->frame_pos = 0;
                v->frame_in_sf = 0;
            } else if (p->eventId == 2) { // Pause
                v->paused = 1;
            } else if (p->eventId == 3) { // Resume
                v->paused = 0;
                v->playing = 1;
            } else if (p->eventId == 4) { // KeyOff
                v->has_loop = 0;
            }
        }
        // 7. Pitch (0x10000005, 0x20000005, 0x20010005, 0x30000005, etc.)
        else if (((id & 0xffff) == 0x0005 || (id & 0xffff) == 0x0006) && id != 0x00000005 && h->size >= 12) {
            float ratio = *(const float *)(cur + 8);
            if (ratio > 0.01f && ratio < 10.0f) {
                v->pitch = ratio;
            }
        }

        if (h->next <= 0 || h->next > 4096) break;
        cur += h->next;
        depth++;
    }

    pthread_mutex_unlock(&s_ngs2_lock);
    return 0;
}

static inline uint64_t ngs2_now_ns(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000000000ULL + (uint64_t)t.tv_nsec;
}

static void ngs2_render_quantum_locked(float *out_float, uint32_t num_frames, int *out_active, float *out_peak) {
    if (!out_float || num_frames == 0) return;

    memset(out_float, 0, num_frames * 8 * sizeof(float));

    int active_voices = 0;
    float peak = 0.0f;

    // Mix all playing sampler voices into out_float
    for (int r = 0; r < NGS2_MAX_RACKS; ++r) {
        uint32_t rtype = s_rack_types[r];
        // Submixer racks (0x3000 / 12288) do not generate waveform audio directly
        if (rtype == 0x3000 || rtype == 12288) continue;

        for (int vi = 0; vi < NGS2_MAX_VOICES_PER_RACK; ++vi) {
            Ngs2Voice *v = &s_voices[r][vi];
            if (!v->in_use || !v->playing || v->paused) continue;

            // Make sure voice has decoded PCM frames ready
            ngs2_voice_decode_more(v);
            if (v->pcm_avail == 0) continue;

            active_voices++;
            uint32_t frames_to_mix = num_frames < v->pcm_avail ? num_frames : v->pcm_avail;

            float vol = (v->volume > 0.0001f) ? v->volume : 1.0f;
            for (uint32_t f = 0; f < frames_to_mix; ++f) {
                uint32_t rpos = (v->pcm_read_pos + f) % NGS2_PCM_RING_FRAMES;
                float l = v->pcm_ring[rpos * 2 + 0] * vol;
                float r = v->pcm_ring[rpos * 2 + 1] * vol;

                out_float[f * 8 + 0] += l; // Front Left
                out_float[f * 8 + 1] += r; // Front Right
            }

            v->pcm_read_pos = (v->pcm_read_pos + frames_to_mix) % NGS2_PCM_RING_FRAMES;
            v->pcm_avail -= frames_to_mix;

            // One-Shot EOF: if non-looping voice reached stream end and buffer drained, stop immediately
            if (!v->has_loop && v->pcm_avail == 0) {
                int channels = v->channels ? v->channels : 2;
                int atrac9_eof = (v->sf_pos >= v->stream_size);
                int pcm_eof = (v->frame_pos * (size_t)channels * sizeof(int16_t) >= v->stream_size);
                if (atrac9_eof || pcm_eof) {
                    v->playing = 0;
                }
            }
        }
    }

    // Apply soft limiter / clamp to [-1.0f, 1.0f] and calculate peak
    for (uint32_t f = 0; f < num_frames; ++f) {
        for (int ch = 0; ch < 2; ++ch) {
            float s = out_float[f * 8 + ch];
            if (s > 1.0f) s = 1.0f;
            else if (s < -1.0f) s = -1.0f;
            out_float[f * 8 + ch] = s;
            float abs_s = fabsf(s);
            if (abs_s > peak) peak = abs_s;
        }
    }

    if (out_active) *out_active = active_voices;
    if (out_peak) *out_peak = peak;
}

static ABI int32_t ngs2_sys_render(uintptr_t sys, const void *buf_info, uint32_t num_buffers) {
    (void)sys;
    if (!buf_info || num_buffers == 0) return 0;

    pthread_mutex_lock(&s_ngs2_lock);
    const struct OrbisNgs2RenderBufferInfo *buffers = (const struct OrbisNgs2RenderBufferInfo *)buf_info;

    // Clear all output buffers first
    for (uint32_t b = 0; b < num_buffers; ++b) {
        if (buffers[b].buffer && buffers[b].bufferSize > 0) {
            memset(buffers[b].buffer, 0, buffers[b].bufferSize);
        }
    }

    // Buffer 0 is the main 8-channel float buffer (256 frames * 8 channels * sizeof(float) = 8192 bytes)
    float *out_float = (float *)buffers[0].buffer;
    uint32_t num_frames = (uint32_t)(buffers[0].bufferSize / (8 * sizeof(float)));
    if (!out_float || num_frames == 0) {
        pthread_mutex_unlock(&s_ngs2_lock);
        return 0;
    }

    // Render the main quantum into buffers[0].buffer (Single Sink Rule)
    int active_voices = 0;
    float peak = 0.0f;
    ngs2_render_quantum_locked(out_float, num_frames, &active_voices, &peak);

    // Mirror to auxiliary render buffers if present
    for (uint32_t b = 1; b < num_buffers; ++b) {
        if (buffers[b].buffer && buffers[b].bufferSize >= buffers[0].bufferSize) {
            memcpy(buffers[b].buffer, buffers[0].buffer, buffers[0].bufferSize);
        }
    }

    // Rate monitor statistics
    if (ngs2_hot_trace()) {
        static uint64_t s_stat_start_ns = 0;
        static uint32_t s_stat_frames = 0;
        static uint32_t s_stat_calls = 0;
        static float s_stat_max_peak = 0.0f;
        uint64_t now = ngs2_now_ns();
        if (s_stat_start_ns == 0) s_stat_start_ns = now;
        s_stat_frames += num_frames;
        s_stat_calls++;
        if (peak > s_stat_max_peak) s_stat_max_peak = peak;

        if (now - s_stat_start_ns >= 1000000000ULL) {
            double elapsed_sec = (double)(now - s_stat_start_ns) / 1000000000.0;
            uint32_t rate_fps = (uint32_t)((double)s_stat_frames / elapsed_sec);
            fprintf(stderr, "[NGS2 Monitor] Rate: %u frames/s, calls: %u/s, active_voices: %d, peak: %.4f\n",
                    rate_fps, s_stat_calls, active_voices, s_stat_max_peak);
            fflush(stderr);
            s_stat_start_ns = now;
            s_stat_frames = 0;
            s_stat_calls = 0;
            s_stat_max_peak = 0.0f;
        }
    }

    static uint32_t s_render_calls = 0;
    s_render_calls++;
    if (ngs2_hot_trace() && (s_render_calls <= 5 || s_render_calls % 300 == 0 || (active_voices > 0 && s_render_calls % 60 == 0) || peak > 0.001f)) {
        static uint32_t s_peak_render_log = 0;
        if (peak > 0.001f) {
            if (s_peak_render_log++ < 25) {
                fprintf(stderr, "[NGS2] Render call=%u active_voices=%d SOUND DETECTED! peak=%.4f (frames=%u -> 8ch float)\n",
                        s_render_calls, active_voices, peak, num_frames);
                fflush(stderr);
            }
        } else {
            fprintf(stderr, "[NGS2] Render call=%u active_voices=%d peak=%.4f (frames=%u -> 8ch float)\n",
                    s_render_calls, active_voices, peak, num_frames);
            fflush(stderr);
        }
    }

    pthread_mutex_unlock(&s_ngs2_lock);
    return 0;
}

#endif /* RUNTIME_NGS2_INC */
