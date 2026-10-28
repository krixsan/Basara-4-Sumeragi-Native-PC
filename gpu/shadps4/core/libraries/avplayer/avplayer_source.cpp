// SPDX-FileCopyrightText: Copyright 2024-2026 shadPS4 Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#include "common/alignment.h"
#include "common/singleton.h"
#include "common/thread.h"
#include "core/libraries/avplayer/avplayer_error.h"
#include "core/libraries/avplayer/avplayer_file_streamer.h"
#include "core/libraries/avplayer/avplayer_source.h"
#include "core/libraries/videodec/video_utils.h"
#include "core/memory.h"

#include <magic_enum/magic_enum.hpp>
#include <deque>
#include <fstream>
#include <sstream>
#include <iomanip>

extern "C" {
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavformat/avio.h>
#include <libavutil/mathematics.h>
#include <libswresample/swresample.h>
#include <libswscale/swscale.h>
}

#include "common/support/avdec.h"

extern "C" int runtime_file_translate(const char* guest, char* out, size_t size);
extern "C" void runtime_audio_stop_movie(void);

namespace Libraries::AvPlayer {

// v2.1.2: Diagnostic instrumentation for video freeze diagnosis
static bool g_avplayer_trace_enabled = false;
static bool g_avplayer_force_deliver = false;
static std::mutex g_trace_ring_mutex;
static std::deque<std::pair<u64, std::string>> g_trace_ring;  // Last 100 events

// Ring buffer event logging
static void LogTraceEvent(const std::string& event) {
    if (!g_avplayer_trace_enabled) return;
    
    std::unique_lock lock(g_trace_ring_mutex);
    auto now = std::chrono::high_resolution_clock::now();
    static auto start = now;
    auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - start).count();
    
    g_trace_ring.emplace_back(elapsed, event);
    if (g_trace_ring.size() > 100) {
        g_trace_ring.pop_front();
    }
}

static void DumpTraceRingToFile() {
    if (!g_avplayer_trace_enabled) return;
    
    std::unique_lock lock(g_trace_ring_mutex);
    std::ofstream log_file("avplayer_trace.log", std::ios::app);
    log_file << "\n========== TRACE RING DUMP (Last 100 Events) ==========\n";
    for (const auto& [timestamp, event] : g_trace_ring) {
        log_file << "[" << std::setw(6) << timestamp << "ms] " << event << "\n";
    }
    log_file << "========================================================\n";
    log_file.close();
    
    fprintf(stderr, "[AV_TRACE] Dumped ring buffer to avplayer_trace.log\n");
}

static void InitTracing() {
    static bool initialized = false;
    if (initialized) return;
    initialized = true;
    
    const char* trace_env = std::getenv("BASARA_AVPLAYER_TRACE");
    g_avplayer_trace_enabled = (trace_env != nullptr && trace_env[0] == '1');
    
    const char* force_env = std::getenv("BASARA_AVPLAYER_FORCE_DELIVER");
    g_avplayer_force_deliver = (force_env != nullptr && force_env[0] == '1');
    
    if (g_avplayer_trace_enabled) {
        fprintf(stderr, "[AV_TRACE] Instrumentation ENABLED (set BASARA_AVPLAYER_TRACE=0 to disable)\n");
        std::ofstream log_file("avplayer_trace.log", std::ios::trunc);
        log_file << "===== Basara 4 AvPlayer Diagnostic Trace =====\n";
        log_file << "Timestamp (ms) | Event\n";
        log_file.close();
    }
    
    if (g_avplayer_force_deliver) {
        fprintf(stderr, "[AV_VIDEO] FORCE_DELIVER ENABLED - timestamp gating BYPASSED (diagnostic mode)\n");
    }
}

static AvPlayerStreamType CodecTypeToStreamType(AVMediaType codec_type) {
    switch (codec_type) {
    case AVMediaType::AVMEDIA_TYPE_VIDEO:
        return AvPlayerStreamType::Video;
    case AVMediaType::AVMEDIA_TYPE_AUDIO:
        return AvPlayerStreamType::Audio;
    case AVMediaType::AVMEDIA_TYPE_SUBTITLE:
        return AvPlayerStreamType::TimedText;
    default:
        LOG_ERROR(Lib_AvPlayer, "Unexpected AVMediaType {}", magic_enum::enum_name(codec_type));
        return AvPlayerStreamType::Unknown;
    }
}

static bool IsStreamSupported(AVStream* stream) {
    const auto codec_id = stream->codecpar->codec_id;
    return codec_id == AV_CODEC_ID_H264 || codec_id == AV_CODEC_ID_HEVC ||
           codec_id == AV_CODEC_ID_AAC;
}

AvPlayerSource::AvPlayerSource(AvPlayerStateCallback& state) : m_state(state) {}

AvPlayerSource::~AvPlayerSource() {
    Stop();
}

bool AvPlayerSource::Init(const AvPlayerInitData& init_data, std::string_view path) {
    m_memory_replacement = init_data.memory_replacement;
    m_max_num_video_framebuffers =
        std::min(std::max(2, init_data.num_output_video_framebuffers), 16);

    AVFormatContext* context = avformat_alloc_context();
    if (context == nullptr) {
        LOG_ERROR(Lib_AvPlayer, "Could not allocate AVFormatContext for {}", path);
        return false;
    }

    const auto attach_custom_io = [&]() {
        context->pb = m_up_data_streamer->GetContext();
        context->flags |= AVFMT_FLAG_CUSTOM_IO;
    };

    if (init_data.file_replacement.open != nullptr) {
        LOG_INFO(Lib_AvPlayer, "Opening {} through the game-provided file replacement", path);
        m_up_data_streamer = std::make_unique<AvPlayerFileStreamer>(init_data.file_replacement);
        if (!m_up_data_streamer->Init(path)) {
            avformat_free_context(context);
            return false;
        }
        attach_custom_io();
        if (AVPLAYER_IS_ERROR(avformat_open_input(&context, nullptr, nullptr, nullptr))) {
            return false;
        }
    } else {
        // engine: guest paths are translated by the port's file system (runtime_file.c).
        char host[1024];
        if (runtime_file_translate(std::string(path).c_str(), host, sizeof(host)) != 0) {
            LOG_ERROR(Lib_AvPlayer, "Cannot translate guest path {}", path);
            avformat_free_context(context);
            return false;
        }
        LOG_INFO(Lib_AvPlayer, "Opening {} from host path {}", path, host);
        if (AVPLAYER_IS_ERROR(avformat_open_input(&context, host, nullptr, nullptr))) {
            return false;
        }
    }
    m_avformat_context = AVFormatContextPtr(context, &ReleaseAVFormatContext);

    return true;
}

bool AvPlayerSource::FindStreams() {
    if (avformat_find_stream_info(m_avformat_context.get(), nullptr) >= 0) {
        m_streams.reserve(m_avformat_context->nb_streams);
        for (u32 idx = 0; idx < m_avformat_context->nb_streams; ++idx) {
            if (!IsStreamSupported(m_avformat_context->streams[idx])) {
                continue;
            }
            m_streams.push_back({idx, CreateStreamInfo(idx)});
        }
    }
    m_duration = DurationMillis();
    return m_streams.size() > 0;
}

s32 AvPlayerSource::GetStreamCount() {
    LOG_INFO(Lib_AvPlayer, "Stream Count: {}", m_streams.size());
    return m_streams.size();
}

static u64 TimestampToMillis(s64 timestamp, AVRational time_base) {
    if (timestamp == AV_NOPTS_VALUE || timestamp <= 0 || time_base.num <= 0 || time_base.den <= 0) {
        return 0;
    }

    const auto millis = av_rescale_q(timestamp, time_base, AVRational{1, 1000});
    return millis > 0 ? u64(millis) : 0;
}

static u64 StreamDurationMillis(const AVFormatContext& context, const AVStream& stream) {
    const auto stream_duration = TimestampToMillis(stream.duration, stream.time_base);
    if (stream_duration != 0) {
        return stream_duration;
    }
    return TimestampToMillis(context.duration, AVRational{1, AV_TIME_BASE});
}

AvPlayerStreamInfo AvPlayerSource::CreateStreamInfo(u32 stream_index) {
    AvPlayerStreamInfo info = {};
    const auto p_stream = m_avformat_context->streams[stream_index];
    info.type = CodecTypeToStreamType(p_stream->codecpar->codec_type);
    info.start_time = 0; // start_time is currently unused and defaults to 0.
    info.duration = StreamDurationMillis(*m_avformat_context, *p_stream);
    const auto p_lang_node = av_dict_get(p_stream->metadata, "language", nullptr, 0);
    if (p_lang_node != nullptr) {
        LOG_INFO(Lib_AvPlayer, "Stream {} language = {}", stream_index, p_lang_node->value);
    } else {
        LOG_WARNING(Lib_AvPlayer, "Stream {} language is unknown", stream_index);
    }
    switch (info.type) {
    case AvPlayerStreamType::Video: {
        LOG_INFO(Lib_AvPlayer, "Stream {} is a video stream.", stream_index);
        info.details.video.aspect_ratio =
            f32(p_stream->codecpar->width) / p_stream->codecpar->height;
        const auto width = Common::AlignUp<u32>(p_stream->codecpar->width, 16);
        const auto height = Common::AlignUp<u32>(p_stream->codecpar->height, 16);
        info.details.video.width = width;
        info.details.video.height = height;
        if (p_lang_node != nullptr) {
            std::memcpy(info.details.video.language_code, p_lang_node->value,
                        std::min(strlen(p_lang_node->value), size_t(3)));
        }
        break;
    }
    case AvPlayerStreamType::Audio: {
        LOG_INFO(Lib_AvPlayer, "Stream {} is an audio stream.", stream_index);
        info.details.audio.channel_count = p_stream->codecpar->ch_layout.nb_channels;
        info.details.audio.sample_rate = p_stream->codecpar->sample_rate;
        info.details.audio.size = 0; // sceAvPlayerGetStreamInfo() is expected to set this to 0
        if (p_lang_node != nullptr) {
            std::memcpy(info.details.audio.language_code, p_lang_node->value,
                        std::min(strlen(p_lang_node->value), size_t(3)));
        }
        break;
    }
    case AvPlayerStreamType::TimedText: {
        info.details.subs.font_size = 12;
        info.details.subs.text_size = 12;
        if (p_lang_node != nullptr) {
            std::memcpy(info.details.subs.language_code, p_lang_node->value,
                        std::min(strlen(p_lang_node->value), size_t(3)));
        }
        break;
    }
    default: {
        UNREACHABLE_MSG("Unknown stream type, codec id {}",
                        magic_enum::enum_name(p_stream->codecpar->codec_type));
    }
    }
    return info;
}

bool AvPlayerSource::GetStreamInfo(u32 stream_index, AvPlayerStreamInfo& info) {
    if (stream_index >= m_streams.size()) {
        LOG_ERROR(Lib_AvPlayer, "Could not get stream {} info.", stream_index);
        return false;
    }
    info = m_streams[stream_index].info;
    return true;
}

bool AvPlayerSource::EnableStream(u32 stream_index) {
    if (m_avformat_context == nullptr || stream_index >= m_streams.size()) {
        return false;
    }
    stream_index = m_streams[stream_index].ffmpeg_index;
    const auto stream = m_avformat_context->streams[stream_index];
    switch (stream->codecpar->codec_type) {
    case AVMediaType::AVMEDIA_TYPE_VIDEO: {
        m_video_stream_index = stream_index;
        LOG_INFO(Lib_AvPlayer, "Video stream {} enabled", stream_index);
        break;
    }
    case AVMediaType::AVMEDIA_TYPE_AUDIO: {
        m_audio_stream_index = stream_index;
        LOG_INFO(Lib_AvPlayer, "Audio stream {} enabled", stream_index);
        break;
    }
    default:
        LOG_WARNING(Lib_AvPlayer, "Unknown stream type {} for stream {}",
                    magic_enum::enum_name(stream->codecpar->codec_type), stream_index);
        break;
    }
    return true;
}

void AvPlayerSource::SetLooping(bool is_looping) {
    m_is_looping = is_looping;
}

std::optional<bool> AvPlayerSource::HasFrames(u32 num_frames) {
    return m_video_packets.Size() > num_frames || m_is_eof;
}

bool AvPlayerSource::Start() {
    std::unique_lock lock(m_state_mutex);

    if (!m_video_stream_index && !m_audio_stream_index) {
        LOG_ERROR(Lib_AvPlayer, "Could not start playback. No streams.");
        return false;
    }
    if (m_video_stream_index) {
        const auto stream_index = m_streams[m_video_stream_index.value()].ffmpeg_index;
        const auto stream = m_avformat_context->streams[stream_index];
        // BUG FIX 2 (P0): Check seek return value
        const auto seek_result = avformat_seek_file(m_avformat_context.get(), m_video_stream_index.value(), 0, 0,
                           stream->duration, 0);
        if (seek_result < 0) {
            LOG_ERROR(Lib_AvPlayer, "Could not seek video stream to start: error = {}", seek_result);
            return false;
        }
        const auto decoder = avcodec_find_decoder(stream->codecpar->codec_id);
        if (decoder == nullptr) {
            return false;
        }
        m_video_codec_context =
            AVCodecContextPtr(avcodec_alloc_context3(decoder), &ReleaseAVCodecContext);
        if (avcodec_parameters_to_context(m_video_codec_context.get(), stream->codecpar) < 0) {
            LOG_ERROR(Lib_AvPlayer, "Could not copy stream {} avcodec parameters to context.",
                      m_video_stream_index.value());
            return false;
        }
        if (avcodec_open2(m_video_codec_context.get(), decoder, nullptr) < 0) {
            LOG_ERROR(Lib_AvPlayer, "Could not open avcodec for video stream {}.",
                      m_video_stream_index.value());
            return false;
        }
        const auto pitch = Common::AlignUp<u32>(m_video_codec_context->width, 64);
        const auto height = Common::AlignUp<u32>(m_video_codec_context->height, 16);
        const auto size = (pitch * height * 3) / 2;
        for (u64 index = 0; index < m_max_num_video_framebuffers; ++index) {
            m_video_buffers.Push(GuestBuffer(m_memory_replacement, 0x100, size, true));
        }
    }
    if (m_audio_stream_index) {
        const auto stream_index = m_streams[m_audio_stream_index.value()].ffmpeg_index;
        const auto stream = m_avformat_context->streams[stream_index];
        // BUG FIX 2 (P0): Check seek return value
        const auto seek_result = avformat_seek_file(m_avformat_context.get(), m_audio_stream_index.value(), 0, 0,
                           stream->duration, 0);
        if (seek_result < 0) {
            LOG_ERROR(Lib_AvPlayer, "Could not seek audio stream to start: error = {}", seek_result);
            return false;
        }
        const auto decoder = avcodec_find_decoder(stream->codecpar->codec_id);
        if (decoder == nullptr) {
            return false;
        }
        m_audio_codec_context =
            AVCodecContextPtr(avcodec_alloc_context3(decoder), &ReleaseAVCodecContext);
        if (avcodec_parameters_to_context(m_audio_codec_context.get(), stream->codecpar) < 0) {
            LOG_ERROR(Lib_AvPlayer, "Could not copy stream {} avcodec parameters to context.",
                      m_audio_stream_index.value());
            return false;
        }
        if (avcodec_open2(m_audio_codec_context.get(), decoder, nullptr) < 0) {
            LOG_ERROR(Lib_AvPlayer, "Could not open avcodec for audio stream {}.",
                      m_audio_stream_index.value());
            return false;
        }
        constexpr u8 max_channels = 8;
        constexpr size_t max_sample_size = sizeof(s32);
        const auto size = max_channels * max_sample_size * 1024;
        for (u64 index = 0; index < (m_max_num_video_framebuffers * 2); ++index) {
            m_audio_buffers.Push(GuestBuffer(m_memory_replacement, 0x10, size, false));
        }
    }
    m_frames_delivered.store(0);
    m_video_frames_delivered.store(0);
    m_demuxer_thread.Run([this](std::stop_token stop) { this->DemuxerThread(stop); });
    m_video_decoder_thread.Run([this](std::stop_token stop) { this->VideoDecoderThread(stop); });
    m_audio_decoder_thread.Run([this](std::stop_token stop) { this->AudioDecoderThread(stop); });
    m_watchdog_thread.Run([this](std::stop_token stop) { this->WatchdogThread(stop); });
    m_start_time = std::chrono::high_resolution_clock::now();
    // Reset timestamp rebase on start
    m_video_ts_rebase.reset();
    m_audio_ts_rebase.reset();
    return true;
}

bool AvPlayerSource::Stop() {
    std::unique_lock lock(m_state_mutex);
    runtime_audio_stop_movie();

    if (!HasRunningThreads()) {
        LOG_WARNING(Lib_AvPlayer, "Could not stop playback: already stopped.");
        return false;
    }

    if (m_up_data_streamer) {
        m_up_data_streamer->Reset();
    }

    m_video_decoder_thread.Stop();
    m_audio_decoder_thread.Stop();
    m_demuxer_thread.Stop();
    m_watchdog_thread.Stop();

    m_current_audio_frame.reset();
    m_current_video_frame.reset();

    m_video_buffers.Clear();
    m_audio_buffers.Clear();
    m_audio_packets.Clear();
    m_video_packets.Clear();
    m_audio_frames.Clear();
    m_video_frames.Clear();

    m_last_audio_ts.reset();
    m_last_data_time.reset();
    m_start_time.reset();
    m_pause_time = {};
    m_pause_duration = {};

    // Reset timestamp rebase on stop
    m_video_ts_rebase.reset();
    m_audio_ts_rebase.reset();

    m_is_paused = false;
    m_is_eof = false;

    return true;
}

void AvPlayerSource::Pause() {
    m_pause_time = std::chrono::high_resolution_clock::now();
    m_is_paused = true;
}

void AvPlayerSource::Resume() {
    m_pause_duration += std::chrono::high_resolution_clock::now() - m_pause_time;
    m_is_paused = false;
}

bool AvPlayerSource::GetVideoData(AvPlayerFrameInfo& video_info) {
    AvPlayerFrameInfoEx info{};
    if (!GetVideoData(info)) {
        return false;
    }
    video_info = {};
    video_info.timestamp = u64(info.timestamp);
    video_info.p_data = reinterpret_cast<u8*>(info.p_data);
    video_info.details.video.aspect_ratio = info.details.video.aspect_ratio;
    video_info.details.video.width = info.details.video.width;
    video_info.details.video.height = info.details.video.height;
    return true;
}

bool AvPlayerSource::GetVideoData(AvPlayerFrameInfoEx& video_info) {
    InitTracing();
    
    // v2.1.2: Entry instrumentation
    if (g_avplayer_trace_enabled) {
        std::ostringstream oss;
        oss << "GetVideoData: entry - video_frames=" << m_video_frames.Size() 
            << " video_buffers=" << m_video_buffers.Size()
            << " current_frame=" << (m_current_video_frame.has_value() ? "yes" : "no");
        LogTraceEvent(oss.str());
    }
    
    if (!IsActive() || m_is_paused) {
        if (g_avplayer_trace_enabled) {
            LogTraceEvent(std::string("GetVideoData: return false - ") + 
                         (!IsActive() ? "not_active" : "paused"));
        }
        return false;
    }

    if (m_video_frames.Size() == 0) {
        if (g_avplayer_trace_enabled) {
            LogTraceEvent("GetVideoData: return false - empty_queue");
        }
        return false;
    }

    const auto current_time = CurrentTime();
    const auto& new_frame = m_video_frames.Front();
    const auto sync_mode = m_state.GetSyncMode();
    
    // v2.1.2: Timestamp gate instrumentation (critical for diagnosis)
    if (sync_mode == AvPlayerAvSyncMode::Default && !g_avplayer_force_deliver) {
        if (new_frame.info.timestamp > current_time) {
            if (g_avplayer_trace_enabled) {
                std::ostringstream oss;
                oss << "GetVideoData: GATED (timestamp=" << new_frame.info.timestamp 
                    << " > current=" << current_time << ")";
                LogTraceEvent(oss.str());
            }
            return false;
        }
    } else if (g_avplayer_force_deliver) {
        if (g_avplayer_trace_enabled) {
            std::ostringstream oss;
            oss << "GetVideoData: FORCE_DELIVER - ts=" << new_frame.info.timestamp 
                << " curr=" << current_time << " (gate bypassed)";
            LogTraceEvent(oss.str());
        }
    }

    if (m_current_video_frame.has_value()) {
        m_video_buffers.Push(std::move(m_current_video_frame->buffer));
        m_current_video_frame.reset();
        m_video_buffers_cv.Notify();
    }

    auto frame = m_video_frames.Pop();
    video_info = frame->info;

    m_current_video_frame = std::move(frame);
    m_frames_delivered.fetch_add(1, std::memory_order_relaxed);
    m_video_frames_delivered.fetch_add(1, std::memory_order_relaxed);
    
    if (g_avplayer_trace_enabled) {
        std::ostringstream oss;
        oss << "GetVideoData: delivered - ts=" << video_info.timestamp
            << " remaining=" << m_video_frames.Size()
            << " buffers=" << m_video_buffers.Size();
        LogTraceEvent(oss.str());
    }
    
    return true;
}

bool AvPlayerSource::GetAudioData(AvPlayerFrameInfo& audio_info) {
    static u64 call_count = 0;
    call_count++;
    
    if (!IsActive() || m_is_paused) {
        return false;
    }

    if (m_audio_frames.Size() == 0) {
        return false;
    }

    if (m_current_audio_frame.has_value()) {
        m_audio_buffers.Push(std::move(m_current_audio_frame->buffer));
        m_current_audio_frame.reset();
        m_audio_buffers_cv.Notify();
    }

    auto frame = m_audio_frames.Pop();
    m_last_audio_ts = frame->info.timestamp;
    m_last_data_time = std::chrono::high_resolution_clock::now();
    m_pause_duration = std::chrono::high_resolution_clock::duration(0);

    audio_info = {};
    audio_info.timestamp = frame->info.timestamp;
    audio_info.p_data = reinterpret_cast<u8*>(frame->info.p_data);
    audio_info.details.audio.sample_rate = frame->info.details.audio.sample_rate;
    audio_info.details.audio.size = frame->info.details.audio.size;
    audio_info.details.audio.channel_count = frame->info.details.audio.channel_count;
    m_current_audio_frame = std::move(frame);
    m_frames_delivered.fetch_add(1, std::memory_order_relaxed);
    
    // v2.1.2: Log first 5 calls and every 60th call
    if (g_avplayer_trace_enabled && (call_count <= 5 || call_count % 60 == 0)) {
        std::ostringstream oss;
        oss << "GetAudioData: call=" << call_count
            << " ts=" << audio_info.timestamp
            << " remaining=" << m_audio_frames.Size();
        LogTraceEvent(oss.str());
    }
    
    return true;
}

u64 AvPlayerSource::DurationMillis() const {
    if (m_avformat_context == nullptr) {
        return 0;
    }

    u64 duration = 0;
    const auto add_stream_duration = [&](std::optional<s32> stream_index) {
        if (!stream_index.has_value()) {
            return;
        }
        if (stream_index.value() < 0) {
            return;
        }
        const auto index = m_streams[stream_index.value()].ffmpeg_index;
        if (index >= m_streams.size()) {
            return;
        }
        const auto stream = m_avformat_context->streams[index];
        if (stream == nullptr) {
            return;
        }
        duration = std::max(duration, StreamDurationMillis(*m_avformat_context, *stream));
    };

    add_stream_duration(m_video_stream_index);
    add_stream_duration(m_audio_stream_index);

    if (duration == 0) {
        for (u32 index = 0; index < m_avformat_context->nb_streams; ++index) {
            const auto stream = m_avformat_context->streams[index];
            if (stream != nullptr) {
                duration = std::max(duration, StreamDurationMillis(*m_avformat_context, *stream));
            }
        }
    }

    return duration;
}

u64 AvPlayerSource::CurrentTime() {
    if (!m_start_time.has_value()) {
        return 0;
    }

    if (m_is_eof && !IsActive()) {
        return m_duration;
    }
    if (!IsActive()) {
        return 0;
    }

    using namespace std::chrono;
    const auto now = m_is_paused.load() ? m_pause_time : high_resolution_clock::now();
    
    // BUG FIX 1 (P0): Audio clock fallback for deadlock prevention
    // If audio stream exists, use audio timing as primary but validate against wall clock
    if (m_audio_stream_index && m_last_data_time.has_value()) {
        const auto audio_elapsed =
            duration_cast<milliseconds>(now - m_last_data_time.value() - m_pause_duration).count();
        const auto audio_time = m_last_audio_ts.value_or(0) + (audio_elapsed > 0 ? u64(audio_elapsed) : 0ULL);
        
        // Compute wall-clock time from m_start_time as fallback
        const auto wall_elapsed =
            duration_cast<milliseconds>(now - m_start_time.value() - m_pause_duration).count();
        const auto wall_time = wall_elapsed > 0 ? u64(wall_elapsed) : 0ULL;
        
        // If audio clock drifts >1000ms from wall clock, use wall clock instead
        // This prevents video playback from blocking when audio pipeline stalls
        const s64 drift = s64(audio_time) - s64(wall_time);
        if (std::abs(drift) > 1000) {
            // Rate-limit logging: max once per 500ms
            static auto last_log_time = high_resolution_clock::now();
            const auto now_log = high_resolution_clock::now();
            if (duration_cast<milliseconds>(now_log - last_log_time).count() >= 500) {
                LOG_WARNING(Lib_AvPlayer, 
                    "[AV_TIMING] Audio clock drift >1s detected, using wall clock (audio={}ms, wall={}ms, drift={}ms)",
                    audio_time, wall_time, drift);
                fprintf(stderr, "[AV_TIMING] Audio clock drift >1s, using wall clock (audio=%llums, wall=%llums)\n", 
                        (unsigned long long)audio_time, (unsigned long long)wall_time);
                last_log_time = now_log;
            }
            return wall_time;
        }
        
        return audio_time;
    }

    const auto elapsed =
        duration_cast<milliseconds>(now - m_start_time.value() - m_pause_duration).count();
    if (elapsed <= 0) {
        return 0;
    }
    const auto current_time = u64(elapsed);
    return m_duration != 0 && current_time > m_duration ? m_duration : current_time;
}

bool AvPlayerSource::IsActive() {
    return !m_is_eof || m_audio_packets.Size() != 0 || m_video_packets.Size() != 0 ||
           m_video_frames.Size() != 0 || m_audio_frames.Size() != 0;
}

void AvPlayerSource::ReleaseAVPacket(AVPacket* packet) {
    if (packet != nullptr) {
        av_packet_free(&packet);
    }
}

void AvPlayerSource::ReleaseAVFrame(AVFrame* frame) {
    if (frame != nullptr) {
        av_frame_free(&frame);
    }
}

void AvPlayerSource::ReleaseAVCodecContext(AVCodecContext* context) {
    if (context != nullptr) {
        avcodec_free_context(&context);
    }
}

void AvPlayerSource::ReleaseSWRContext(SwrContext* context) {
    if (context != nullptr) {
        swr_free(&context);
    }
}

void AvPlayerSource::ReleaseSWSContext(SwsContext* context) {
    if (context != nullptr) {
        sws_freeContext(context);
    }
}

void AvPlayerSource::ReleaseAVFormatContext(AVFormatContext* context) {
    if (context != nullptr) {
        avformat_close_input(&context);
    }
}

void AvPlayerSource::DemuxerThread(std::stop_token stop) {
    using namespace std::chrono;
    Common::SetCurrentThreadName("shadPS4:AvDemuxer");

    InitTracing(); // v2.1.2: tracing init

    if (!m_audio_stream_index.has_value() && !m_video_stream_index.has_value()) {
        LOG_WARNING(Lib_AvPlayer, "Could not start DEMUXER thread. No streams enabled.");
        return;
    }
    LOG_INFO(Lib_AvPlayer, "Demuxer Thread started");
    auto last_status_time = steady_clock::now(); // v2.1.2: periodic status timer

    while (!stop.stop_requested()) {
        // v2.1.2: Periodic status dump
        if (g_avplayer_trace_enabled) {
            auto now = steady_clock::now();
            if (duration_cast<seconds>(now - last_status_time).count() >= 5) {
                std::ostringstream oss;
                oss << "DemuxerThread: status - video_packets=" << m_video_packets.Size()
                    << " audio_packets=" << m_audio_packets.Size()
                    << " video_frames=" << m_video_frames.Size()
                    << " audio_frames=" << m_audio_frames.Size();
                LogTraceEvent(oss.str());
                last_status_time = now;
            }
        }
        if (m_video_packets.Size() > 30 &&
            (!m_audio_stream_index.has_value() || m_audio_packets.Size() > 8)) {
            std::this_thread::sleep_for(milliseconds(5));
            continue;
        }
        AVPacketPtr up_packet(av_packet_alloc(), &ReleaseAVPacket);
        const auto res = av_read_frame(m_avformat_context.get(), up_packet.get());
        if (res < 0) {
            if (res == AVERROR_EOF) {
                if (m_is_looping) {
                    LOG_INFO(Lib_AvPlayer, "EOF reached in demuxer. Looping the source...");
                    m_state.OnWarning(ORBIS_AVPLAYER_ERROR_WAR_LOOPING_BACK);
                    avio_seek(m_avformat_context->pb, 0, SEEK_SET);
                    // Reset timestamp rebase on loop seek
                    m_video_ts_rebase.reset();
                    m_audio_ts_rebase.reset();
                    if (m_video_stream_index.has_value()) {
                        const auto index = m_streams[m_video_stream_index.value()].ffmpeg_index;
                        const auto stream = m_avformat_context->streams[index];
                        // BUG FIX 2 (P0): Check seek return for loop recovery
                        if (avformat_seek_file(m_avformat_context.get(), index, 0, 0, stream->duration, 0) < 0) {
                            LOG_WARNING(Lib_AvPlayer, "Could not seek video stream for loop recovery");
                        }
                    }
                    if (m_audio_stream_index.has_value()) {
                        const auto index = m_streams[m_audio_stream_index.value()].ffmpeg_index;
                        const auto stream = m_avformat_context->streams[index];
                        // BUG FIX 2 (P0): Check seek return for loop recovery
                        if (avformat_seek_file(m_avformat_context.get(), index, 0, 0, stream->duration, 0) < 0) {
                            LOG_WARNING(Lib_AvPlayer, "Could not seek audio stream for loop recovery");
                        }
                    }
                    continue;
                } else {
                    LOG_INFO(Lib_AvPlayer, "EOF reached in demuxer. Exiting.");
                    break;
                }
            } else {
                LOG_ERROR(Lib_AvPlayer, "Could not read AV frame: error = {}", res);
                // BUG FIX 2 (P0): Set EOF before error callback to unblock game
                m_is_eof = true;
                m_state.OnError();
                return;
            }
            break;
        }
        if (up_packet->stream_index == m_video_stream_index) {
            m_video_packets.Push(std::move(up_packet));
            m_video_packets_cv.Notify();
        } else if (up_packet->stream_index == m_audio_stream_index) {
            m_audio_packets.Push(std::move(up_packet));
            m_audio_packets_cv.Notify();
        }
    }

    m_is_eof = true;

    m_video_packets_cv.Notify();
    m_audio_packets_cv.Notify();
    m_video_frames_cv.Notify();
    m_audio_frames_cv.Notify();
    m_video_buffers_cv.Notify();
    m_audio_buffers_cv.Notify();

    m_state.OnEOF();

    LOG_INFO(Lib_AvPlayer, "Demuxer Thread exited normally");
}

AvPlayerSource::AVFramePtr AvPlayerSource::ConvertVideoFrame(const AVFrame& frame) {
    auto nv12_frame = AVFramePtr{av_frame_alloc(), &ReleaseAVFrame};
    nv12_frame->best_effort_timestamp = frame.best_effort_timestamp;
    nv12_frame->pts = frame.pts;
    nv12_frame->pkt_dts = frame.pkt_dts < 0 ? 0 : frame.pkt_dts;
    nv12_frame->format = AV_PIX_FMT_NV12;
    nv12_frame->width = frame.width;
    nv12_frame->height = frame.height;
    nv12_frame->sample_aspect_ratio = frame.sample_aspect_ratio;
    nv12_frame->crop_top = frame.crop_top;
    nv12_frame->crop_bottom = frame.crop_bottom;
    nv12_frame->crop_left = frame.crop_left;
    nv12_frame->crop_right = frame.crop_right;

    av_frame_get_buffer(nv12_frame.get(), 0);

    if (m_sws_context == nullptr) {
        m_sws_context =
            SWSContextPtr(sws_getContext(frame.width, frame.height, AVPixelFormat(frame.format),
                                         nv12_frame->width, nv12_frame->height, AV_PIX_FMT_NV12,
                                         SWS_FAST_BILINEAR, nullptr, nullptr, nullptr),
                          &ReleaseSWSContext);
    }
    const auto res = sws_scale(m_sws_context.get(), frame.data, frame.linesize, 0, frame.height,
                               nv12_frame->data, nv12_frame->linesize);
    if (res < 0) {
        LOG_ERROR(Lib_AvPlayer, "Could not convert to NV12: {}", av_err2str(res));
        return AVFramePtr{nullptr, &ReleaseAVFrame};
    }
    return nv12_frame;
}

static u64 FrameTimestampMillis(const AVFrame& frame, AVRational time_base) {
    auto timestamp = frame.best_effort_timestamp;
    if (timestamp == AV_NOPTS_VALUE) {
        timestamp = frame.pts;
    }
    if (timestamp == AV_NOPTS_VALUE) {
        timestamp = frame.pkt_dts;
    }
    if (timestamp == AV_NOPTS_VALUE || timestamp < 0 || time_base.den <= 0) {
        return 0;
    }

    const auto millis = av_rescale_q(timestamp, time_base, AVRational{1, 1000});
    return millis > 0 ? u64(millis) : 0;
}

Frame AvPlayerSource::PrepareVideoFrame(GuestBuffer buffer, const AVFrame& frame) {
    ASSERT(frame.format == AV_PIX_FMT_NV12);

    auto p_buffer = buffer.GetBuffer();
    Videodec::CopyNV12Data(p_buffer, buffer.Size(), frame);

    const auto stream_index = m_streams[m_video_stream_index.value()].ffmpeg_index;
    const auto stream = m_avformat_context->streams[stream_index];
    const auto timestamp = FrameTimestampMillis(frame, stream->time_base);

    // Timestamp rebase: align PTS to wall clock after seek
    u64 rebased_timestamp = timestamp;
    if (!m_video_ts_rebase.has_value()) {
        m_video_ts_rebase = timestamp;
        LOG_DEBUG(Lib_AvPlayer, "Video TS rebase baseline set: {} ms", timestamp);
    }
    rebased_timestamp = timestamp - m_video_ts_rebase.value();

    const auto width = Common::AlignUp<u32>(frame.width, 16);
    const auto pitch = Common::AlignUp<u32>(frame.width, 64);
    const auto height = Common::AlignUp<u32>(frame.height, 16);
    Core::Memory::Instance()->InvalidateMemory(reinterpret_cast<VAddr>(p_buffer),
                                               (width * height * 3) / 2);

    return Frame{
        .buffer = std::move(buffer),
        .info =
            {
                .p_data = p_buffer,
                .timestamp = rebased_timestamp,
                .details =
                    {
                        .video =
                            {
                                .width = width,
                                .height = height,
                                .aspect_ratio = (float)av_q2d(frame.sample_aspect_ratio),
                                .crop_left_offset = u32(frame.crop_left),
                                .crop_right_offset = u32(frame.crop_right + (pitch - frame.width)),
                                .crop_top_offset = u32(frame.crop_top),
                                .crop_bottom_offset =
                                    u32(frame.crop_bottom + (height - frame.height)),
                                .pitch = pitch,
                                .luma_bit_depth = 8,
                                .chroma_bit_depth = 8,
                            },
                    },
            },
    };
}

void AvPlayerSource::VideoDecoderThread(std::stop_token stop) {
    using namespace std::chrono;
    Common::SetCurrentThreadName("shadPS4:AvVideoDecoder");
    
    InitTracing();

    LOG_INFO(Lib_AvPlayer, "Video Decoder Thread started");
    u64 frames_decoded = 0;
    auto last_status_time = steady_clock::now();
    
    while ((!m_is_eof || m_video_packets.Size() != 0) && !stop.stop_requested()) {
        if (m_video_packets.Size() == 0 &&
            !m_video_packets_cv.WaitFor(stop, std::chrono::milliseconds(200), [this] { return m_video_packets.Size() != 0; })) {
            // v2.1.2: Periodic status dump
            auto now = steady_clock::now();
            if (duration_cast<seconds>(now - last_status_time).count() >= 5) {
                if (g_avplayer_trace_enabled) {
                    std::ostringstream oss;
                    oss << "VideoDecoderThread: STALL - packets=" << m_video_packets.Size()
                        << " frames=" << m_video_frames.Size()
                        << " buffers=" << m_video_buffers.Size()
                        << " decoded=" << frames_decoded;
                    LogTraceEvent(oss.str());
                }
                last_status_time = now;
            }
            continue;
        }
        
        const auto packet = m_video_packets.Pop();
        if (!packet.has_value()) {
            continue;
        }
        
        // v2.1.2: Log packet info
        if (g_avplayer_trace_enabled) {
            std::ostringstream oss;
            oss << "VideoDecoderThread: packet pts=" << packet->get()->pts
                << " dts=" << packet->get()->dts
                << " size=" << packet->get()->size;
            LogTraceEvent(oss.str());
        }

        auto res = avcodec_send_packet(m_video_codec_context.get(), packet->get());
        if (res < 0 && res != AVERROR(EAGAIN)) {
            if (g_avplayer_trace_enabled) {
                LogTraceEvent(std::string("VideoDecoderThread: send_packet ERROR ") + av_err2str(res));
            }
            m_state.OnError();
            LOG_ERROR(Lib_AvPlayer, "Could not send packet to the video codec. Error = {}",
                      av_err2str(res));
            return;
        }
        
        // v2.1.2: Log EAGAIN
        if (res == AVERROR(EAGAIN)) {
            if (g_avplayer_trace_enabled) {
                LogTraceEvent("VideoDecoderThread: send_packet EAGAIN (decoder busy)");
            }
        }
        
        while (res >= 0) {
            if (m_video_buffers.Size() == 0 &&
                !m_video_buffers_cv.WaitFor(stop, std::chrono::milliseconds(200), [this] { return m_video_buffers.Size() != 0; })) {
                // v2.1.2: Buffer exhaustion diagnostic
                if (g_avplayer_trace_enabled) {
                    std::ostringstream oss;
                    oss << "VideoDecoderThread: BUFFER STALL - no buffers after 200ms"
                        << " frames=" << m_video_frames.Size()
                        << " buffers=" << m_video_buffers.Size();
                    LogTraceEvent(oss.str());
                    fprintf(stderr, "[AV_VIDEO] %s\n", oss.str().c_str());
                }
                break;
            }
            
            auto up_frame = AVFramePtr(av_frame_alloc(), &ReleaseAVFrame);
            res = avcodec_receive_frame(m_video_codec_context.get(), up_frame.get());
            if (res < 0) {
                if (res == AVERROR_EOF) {
                    if (g_avplayer_trace_enabled) {
                        LogTraceEvent("VideoDecoderThread: receive_frame EOF");
                    }
                    LOG_INFO(Lib_AvPlayer, "EOF reached in video decoder");
                    return;
                } else if (res != AVERROR(EAGAIN)) {
                    if (g_avplayer_trace_enabled) {
                        LogTraceEvent(std::string("VideoDecoderThread: receive_frame ERROR ") + av_err2str(res));
                    }
                    LOG_ERROR(Lib_AvPlayer,
                              "Could not receive frame from the video codec. Error = {}",
                              av_err2str(res));
                    m_state.OnError();
                    return;
                }
            } else {
                frames_decoded++;
                
                auto buffer = m_video_buffers.Pop();
                if (!buffer.has_value()) {
                    // Video buffers queue was cleared. This means that player was stopped.
                    if (g_avplayer_trace_enabled) {
                        LogTraceEvent("VideoDecoderThread: buffers cleared (player stopped)");
                    }
                    break;
                }
                
                // v2.1.2: Log frame decode success
                if (g_avplayer_trace_enabled) {
                    std::ostringstream oss;
                    oss << "VideoDecoderThread: decoded frame pts=" << up_frame->pts
                        << " format=" << up_frame->format
                        << " total_decoded=" << frames_decoded;
                    LogTraceEvent(oss.str());
                }
                
                if (up_frame->format != AV_PIX_FMT_NV12) {
                    const auto nv12_frame = ConvertVideoFrame(*up_frame);
                    if (nv12_frame == nullptr) {
                        m_state.OnError();
                        return;
                    }
                    m_video_frames.Push(PrepareVideoFrame(std::move(buffer.value()), *nv12_frame));
                } else {
                    m_video_frames.Push(PrepareVideoFrame(std::move(buffer.value()), *up_frame));
                }
                m_video_frames_cv.Notify();
                
                // v2.1.2: Log frame queue size after push
                if (g_avplayer_trace_enabled) {
                    std::ostringstream oss;
                    oss << "VideoDecoderThread: pushed frame - queue=" << m_video_frames.Size();
                    LogTraceEvent(oss.str());
                }
            }
        }
    }

    LOG_INFO(Lib_AvPlayer, "Video Decoder Thread exited normally");
    
    if (g_avplayer_trace_enabled) {
        std::ostringstream oss;
        oss << "VideoDecoderThread: EXIT - total_decoded=" << frames_decoded;
        LogTraceEvent(oss.str());
    }
}

AvPlayerSource::AVFramePtr AvPlayerSource::ConvertAudioFrame(const AVFrame& frame) {
    auto pcm16_frame = AVFramePtr{av_frame_alloc(), &ReleaseAVFrame};
    pcm16_frame->best_effort_timestamp = frame.best_effort_timestamp;
    pcm16_frame->pts = frame.pts;
    pcm16_frame->pkt_dts = frame.pkt_dts < 0 ? 0 : frame.pkt_dts;
    pcm16_frame->format = AV_SAMPLE_FMT_S16;
    /* The guest audio sink is fixed at 48 kHz stereo; make swresample produce exactly that so
     * runtime_audio_play_movie_pcm16 receives interleaved S16 stereo without a second,
     * potentially drifting conversion. PrepareAudioFrame then reports size = samples * 2 * 2. */
    av_channel_layout_default(&pcm16_frame->ch_layout, 2);
    pcm16_frame->sample_rate = 48000;

    if (m_swr_context == nullptr) {
        SwrContext* swr_context = nullptr;
        AVChannelLayout in_ch_layout = frame.ch_layout;
        AVChannelLayout out_ch_layout{};
        av_channel_layout_default(&out_ch_layout, 2);
        swr_alloc_set_opts2(&swr_context, &out_ch_layout, AV_SAMPLE_FMT_S16, 48000,
                            &in_ch_layout, AVSampleFormat(frame.format), frame.sample_rate, 0,
                            nullptr);
        m_swr_context = SWRContextPtr(swr_context, &ReleaseSWRContext);
        swr_init(m_swr_context.get());
    }
    const auto res = swr_convert_frame(m_swr_context.get(), pcm16_frame.get(), &frame);
    if (res < 0) {
        LOG_ERROR(Lib_AvPlayer, "Could not convert to S16 stereo 48 kHz: {}", av_err2str(res));
        return AVFramePtr{nullptr, &ReleaseAVFrame};
    }
    return pcm16_frame;
}

Frame AvPlayerSource::PrepareAudioFrame(GuestBuffer buffer, const AVFrame& frame) {
    ASSERT(frame.format == AV_SAMPLE_FMT_S16);

    auto p_buffer = buffer.GetBuffer();
    const auto channels = frame.ch_layout.nb_channels > 0 ? frame.ch_layout.nb_channels : 2;
    const auto max_samples = buffer.Size() / (channels * sizeof(u16));
    const auto samples_to_copy = std::min<size_t>((size_t)frame.nb_samples, max_samples);
    const auto size = channels * samples_to_copy * sizeof(u16);
    std::memcpy(p_buffer, frame.data[0], size);

    const auto stream_index = m_streams[m_audio_stream_index.value()].ffmpeg_index;
    const auto stream = m_avformat_context->streams[stream_index];
    const auto timestamp = FrameTimestampMillis(frame, stream->time_base);

    // Timestamp rebase: align PTS to wall clock after seek
    u64 rebased_timestamp = timestamp;
    if (!m_audio_ts_rebase.has_value()) {
        m_audio_ts_rebase = timestamp;
        LOG_DEBUG(Lib_AvPlayer, "Audio TS rebase baseline set: {} ms", timestamp);
    }
    rebased_timestamp = timestamp - m_audio_ts_rebase.value();

    return Frame{
        .buffer = std::move(buffer),
        .info =
            {
                .p_data = p_buffer,
                .timestamp = rebased_timestamp,
                .details =
                    {
                        .audio =
                            {
                                .channel_count = u16(frame.ch_layout.nb_channels),
                                .sample_rate = u32(frame.sample_rate),
                                .size = u32(size),
                            },
                    },
            },
    };
}

void AvPlayerSource::AudioDecoderThread(std::stop_token stop) {
    using namespace std::chrono;
    Common::SetCurrentThreadName("shadPS4:AvAudioDecoder");

    LOG_INFO(Lib_AvPlayer, "Audio Decoder Thread started");
    while ((!m_is_eof || m_audio_packets.Size() != 0) && !stop.stop_requested()) {
        if (m_audio_packets.Size() == 0 &&
            !m_audio_packets_cv.WaitFor(stop, std::chrono::milliseconds(200), [this] { return m_audio_packets.Size() != 0; })) {
            continue;
        }
        const auto packet = m_audio_packets.Pop();
        if (!packet.has_value()) {
            continue;
        }
        auto res = avcodec_send_packet(m_audio_codec_context.get(), packet->get());
        if (res < 0 && res != AVERROR(EAGAIN)) {
            m_state.OnError();
            LOG_ERROR(Lib_AvPlayer, "Could not send packet to the audio codec. Error = {}",
                      av_err2str(res));
            return;
        }
        while (res >= 0) {
            if (m_audio_buffers.Size() == 0 &&
                !m_audio_buffers_cv.WaitFor(stop, std::chrono::milliseconds(200), [this] { return m_audio_buffers.Size() != 0; })) {
                break;
            }

            auto up_frame = AVFramePtr(av_frame_alloc(), &ReleaseAVFrame);
            res = avcodec_receive_frame(m_audio_codec_context.get(), up_frame.get());
            if (res < 0) {
                if (res == AVERROR_EOF) {
                    LOG_INFO(Lib_AvPlayer, "EOF reached in audio decoder");
                    return;
                } else if (res != AVERROR(EAGAIN)) {
                    m_state.OnError();
                    LOG_ERROR(Lib_AvPlayer,
                              "Could not receive frame from the audio codec. Error = {}",
                              av_err2str(res));
                    return;
                }
            } else {
                auto buffer = m_audio_buffers.Pop();
                if (!buffer.has_value()) {
                    // Audio buffers queue was cleared. This means that player was stopped.
                    break;
                }
                if (up_frame->format != AV_SAMPLE_FMT_S16) {
                    const auto pcm16_frame = ConvertAudioFrame(*up_frame);
                    // BUG FIX 4 (P1): Null check for audio frame conversion
                    if (pcm16_frame == nullptr) {
                        LOG_ERROR(Lib_AvPlayer, "Could not convert audio frame to S16 format");
                        m_state.OnError();
                        return;
                    }
                    m_audio_frames.Push(PrepareAudioFrame(std::move(buffer.value()), *pcm16_frame));
                } else {
                    m_audio_frames.Push(PrepareAudioFrame(std::move(buffer.value()), *up_frame));
                }
                m_audio_frames_cv.Notify();
            }
        }
    }

    LOG_INFO(Lib_AvPlayer, "Audio Decoder Thread exited normally");
}

bool AvPlayerSource::HasRunningThreads() const {
    return m_demuxer_thread.Joinable() || m_video_decoder_thread.Joinable() ||
           m_audio_decoder_thread.Joinable() || m_watchdog_thread.Joinable();
}

void AvPlayerSource::WatchdogThread(std::stop_token stop) {
    using namespace std::chrono;
    Common::SetCurrentThreadName("shadPS4:AvWatchdog");

    LOG_INFO(Lib_AvPlayer, "Watchdog Thread started (auto-skip cutscene freeze)");
    u64 last_delivered = 0;
    auto last_check = steady_clock::now();
    
    while (!stop.stop_requested()) {
        std::this_thread::sleep_for(milliseconds(500));
        
        if (m_is_eof) {
            continue;
        }
        
        const u64 delivered_now = m_video_frames_delivered.load(std::memory_order_relaxed);
        const auto now = steady_clock::now();
        const auto elapsed = duration_cast<milliseconds>(now - last_check).count();
        
        // NEW: If paused, check pause duration separately
        if (m_is_paused.load()) {
            auto pause_start = m_pause_time;
            if (pause_start != high_resolution_clock::time_point{}) {
                const auto now_hr = high_resolution_clock::now();
                auto paused_ms = duration_cast<milliseconds>(now_hr - pause_start).count();
                if (paused_ms > 5000) {
                    LOG_WARNING(Lib_AvPlayer,
                        "[AV_WATCHDOG] Stuck pause detected ({} ms paused, cur_t frozen, no video). Force-unpausing.",
                        paused_ms);
                    fprintf(stderr, "[AV_WATCHDOG] STUCK PAUSE: %lld ms, forcing unpause to trigger skip\n",
                            (long long)paused_ms);
                    // Force clear pause state — this lets GetVideoData proceed
                    // (which will fail because no frames, but now watchdog below can see no video)
                    m_is_paused.store(false);
                    m_pause_duration += now_hr - pause_start;
                    m_pause_time = {};
                    last_check = steady_clock::now();
                }
            } else {
                m_pause_time = high_resolution_clock::now();
            }
            continue;
        }
        
        // Auto-skip cutscene freeze: no video frames delivered for > 3s
        if (delivered_now == last_delivered && elapsed > 3000) {
            fprintf(stderr, "[AV_WATCHDOG] DEADLOCK DETECTED: No video frames delivered for %lld ms. Auto-stopping cutscene.\n", (long long)elapsed);
            LOG_ERROR(Lib_AvPlayer, "Watchdog detected deadlock: no frames for {} ms. Force-stopping playback.", elapsed);
            
            // v2.1.2: Dump diagnostic summary before stopping
            if (g_avplayer_trace_enabled) {
                DumpTraceRingToFile();
            }
            fprintf(stderr, "\n[AV_WATCHDOG] SUMMARY:\n");
            fprintf(stderr, "  Video frames in queue: %zu\n", (size_t)m_video_frames.Size());
            fprintf(stderr, "  Audio frames in queue: %zu\n", (size_t)m_audio_frames.Size());
            fprintf(stderr, "  Video buffers available: %zu\n", (size_t)m_video_buffers.Size());
            fprintf(stderr, "  Audio buffers available: %zu\n", (size_t)m_audio_buffers.Size());
            fprintf(stderr, "  Frames delivered: %llu\n", (unsigned long long)delivered_now);
            fprintf(stderr, "  Sync mode: 0x%x\n", (unsigned)m_state.GetSyncMode());
            fprintf(stderr, "  Set BASARA_AVPLAYER_TRACE=1 for detailed event log\n");
            fprintf(stderr, "\n");
            
            // Force stop to unblock game
            std::unique_lock lock(m_state_mutex);
            m_state.OnError();
            break;
        }
        
        if (delivered_now != last_delivered) {
            last_delivered = delivered_now;
            last_check = now;
        }
    }
    
    LOG_INFO(Lib_AvPlayer, "Watchdog Thread exited");
}

} // namespace Libraries::AvPlayer
