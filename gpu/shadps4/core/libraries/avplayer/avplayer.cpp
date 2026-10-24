// SPDX-FileCopyrightText: Copyright 2024 shadPS4 Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#include "common/logging/log.h"
#include "core/libraries/avplayer/avplayer.h"
#include "core/libraries/avplayer/avplayer_error.h"
#include "core/libraries/avplayer/avplayer_impl.h"
#include "core/libraries/libs.h"

#include <cstdlib>
#include <cstring>
#include <string_view>
#include <chrono>
#include <thread>
#include <atomic>
#include <mutex>
#include <unordered_map>
#include <unordered_set>
#include <memory>

extern "C" void runtime_audio_play_movie_pcm16(const void* pcm16, uint32_t size_bytes,
                                               uint32_t channels, uint32_t sample_rate);
extern "C" void runtime_audio_stop_movie(void);

namespace Libraries::AvPlayer {

namespace {
struct StubAvPlayer {
    AvPlayerInitData init_data{};
    std::atomic<bool> closed{false};
};

static std::mutex s_stub_mutex;
static std::unordered_map<AvPlayerHandle, std::shared_ptr<StubAvPlayer>> s_stub_map;

static std::mutex s_players_mutex;
static std::unordered_set<AvPlayerHandle> s_active_players;

static bool IsActivePlayer(AvPlayerHandle handle) {
    if (!handle) return false;
    std::lock_guard lock(s_players_mutex);
    return s_active_players.find(handle) != s_active_players.end();
}

static void RegisterActivePlayer(AvPlayerHandle handle) {
    if (!handle) return;
    std::lock_guard lock(s_players_mutex);
    s_active_players.insert(handle);
}

static bool UnregisterActivePlayer(AvPlayerHandle handle) {
    if (!handle) return false;
    std::lock_guard lock(s_players_mutex);
    return s_active_players.erase(handle) > 0;
}

bool AvPlayerBypassEnabled() {
    const char* env = std::getenv("BB_ENABLE_AVPLAYER");
    if (env && env[0] == '0') {
        return true;
    }
    return false;
}

extern "C" void runtime_thread_attach_host(const char* name);

static void StubEmitEvent(std::weak_ptr<StubAvPlayer> weak_stub, AvPlayerEvents event) {
    auto stub = weak_stub.lock();
    if (!stub || stub->closed.load(std::memory_order_acquire)) return;
    auto cb = stub->init_data.event_replacement.event_callback;
    void* ptr = stub->init_data.event_replacement.object_ptr;
    std::fprintf(stderr, "[AvPlayer] StubEmitEvent(event=0x%x, cb=%p, obj=%p)\n", (unsigned)event, (void*)cb, ptr);
    std::fflush(stderr);
    if (cb && !stub->closed.load(std::memory_order_acquire)) {
        LOG_INFO(Lib_AvPlayer, "StubAvPlayer: notifying game with event 0x{:x}", u32(event));
        cb(ptr, event, 0, nullptr);
        std::fprintf(stderr, "[AvPlayer] StubEmitEvent(event=0x%x) callback returned\n", (unsigned)event);
        std::fflush(stderr);
    }
}
} // namespace

s32 PS4_SYSV_ABI sceAvPlayerAddSource(AvPlayerHandle handle, const char* filename) {
    std::fprintf(stderr, "[AvPlayer] sceAvPlayerAddSource(handle=%p, file='%s')\n", (void*)handle, filename ? filename : "(null)");
    std::fflush(stderr);
    LOG_TRACE(Lib_AvPlayer, "filename = {}", filename ? filename : "(null)");
    if (handle == nullptr || (!AvPlayerBypassEnabled() && !IsActivePlayer(handle))) {
        return ORBIS_AVPLAYER_ERROR_INVALID_PARAMS;
    }
    if (AvPlayerBypassEnabled()) {
        std::printf("Runtime: AvPlayerAddSource(%s) bypassed (non-blocking finished state)\n",
                    filename ? filename : "(null)");
        std::shared_ptr<StubAvPlayer> stub;
        {
            std::lock_guard lock(s_stub_mutex);
            auto it = s_stub_map.find(handle);
            if (it != s_stub_map.end()) {
                stub = it->second;
            }
        }
        if (stub) {
            std::thread([weak_stub = std::weak_ptr<StubAvPlayer>(stub)] {
                runtime_thread_attach_host("AvPlayerHost");
                std::this_thread::sleep_for(std::chrono::milliseconds(20));
                StubEmitEvent(weak_stub, AvPlayerEvents::StateReady);
            }).detach();
        }
        return ORBIS_OK;
    }
    return handle->AddSource(filename);
}

s32 PS4_SYSV_ABI sceAvPlayerAddSourceEx(AvPlayerHandle handle, AvPlayerUriType uri_type,
                                        AvPlayerSourceDetails* source_details) {
    LOG_TRACE(Lib_AvPlayer, "called");
    if (handle == nullptr || uri_type != AvPlayerUriType::Source || source_details == nullptr ||
        (!AvPlayerBypassEnabled() && !IsActivePlayer(handle))) {
        return ORBIS_AVPLAYER_ERROR_INVALID_PARAMS;
    }
    if (AvPlayerBypassEnabled()) {
        std::shared_ptr<StubAvPlayer> stub;
        {
            std::lock_guard lock(s_stub_mutex);
            auto it = s_stub_map.find(handle);
            if (it != s_stub_map.end()) {
                stub = it->second;
            }
        }
        if (stub) {
            std::thread([weak_stub = std::weak_ptr<StubAvPlayer>(stub)] {
                runtime_thread_attach_host("AvPlayerHost");
                std::this_thread::sleep_for(std::chrono::milliseconds(20));
                StubEmitEvent(weak_stub, AvPlayerEvents::StateReady);
            }).detach();
        }
        return ORBIS_OK;
    }
    const auto path = std::string_view(source_details->uri.name, source_details->uri.length);
    return handle->AddSourceEx(path, source_details->source_type);
}

int PS4_SYSV_ABI sceAvPlayerChangeStream() {
    LOG_ERROR(Lib_AvPlayer, "(STUBBED) called");
    return ORBIS_OK;
}

s32 PS4_SYSV_ABI sceAvPlayerClose(AvPlayerHandle handle) {
    std::fprintf(stderr, "[AvPlayer] sceAvPlayerClose(handle=%p)\n", (void*)handle);
    std::fflush(stderr);
    LOG_TRACE(Lib_AvPlayer, "called");
    if (handle == nullptr) {
        return ORBIS_AVPLAYER_ERROR_INVALID_PARAMS;
    }
    if (AvPlayerBypassEnabled()) {
        std::shared_ptr<StubAvPlayer> stub;
        {
            std::lock_guard lock(s_stub_mutex);
            auto it = s_stub_map.find(handle);
            if (it != s_stub_map.end()) {
                stub = it->second;
                s_stub_map.erase(it);
            }
        }
        if (stub) {
            stub->closed.store(true, std::memory_order_release);
        }
        return ORBIS_OK;
    }
    if (!UnregisterActivePlayer(handle)) {
        LOG_WARNING(Lib_AvPlayer, "sceAvPlayerClose called on already closed or invalid handle %p", (void*)handle);
        return ORBIS_OK;
    }
    runtime_audio_stop_movie();
    delete handle;
    return ORBIS_OK;
}

u64 PS4_SYSV_ABI sceAvPlayerCurrentTime(AvPlayerHandle handle) {
    LOG_TRACE(Lib_AvPlayer, "called");
    if (handle == nullptr || (!AvPlayerBypassEnabled() && !IsActivePlayer(handle))) {
        return 0;
    }
    if (AvPlayerBypassEnabled()) {
        return 0;
    }
    return handle->CurrentTime();
}

s32 PS4_SYSV_ABI sceAvPlayerDisableStream(AvPlayerHandle handle, u32 stream_id) {
    LOG_ERROR(Lib_AvPlayer, "(STUBBED) called");
    if (handle == nullptr || (!AvPlayerBypassEnabled() && !IsActivePlayer(handle))) {
        return ORBIS_AVPLAYER_ERROR_INVALID_PARAMS;
    }
    return ORBIS_OK;
}

s32 PS4_SYSV_ABI sceAvPlayerEnableStream(AvPlayerHandle handle, u32 stream_id) {
    LOG_TRACE(Lib_AvPlayer, "stream_id = {}", stream_id);
    if (handle == nullptr || (!AvPlayerBypassEnabled() && !IsActivePlayer(handle))) {
        return ORBIS_AVPLAYER_ERROR_INVALID_PARAMS;
    }
    if (AvPlayerBypassEnabled()) {
        return ORBIS_OK;
    }
    return handle->EnableStream(stream_id);
}

bool PS4_SYSV_ABI sceAvPlayerGetAudioData(AvPlayerHandle handle, AvPlayerFrameInfo* p_info) {
    LOG_TRACE(Lib_AvPlayer, "called");
    if (handle == nullptr || p_info == nullptr || (!AvPlayerBypassEnabled() && !IsActivePlayer(handle))) {
        return false;
    }
    if (AvPlayerBypassEnabled()) {
        return false;
    }
    bool ok = handle->GetAudioData(*p_info);
    if (ok && p_info->p_data && p_info->details.audio.size > 0) {
        runtime_audio_play_movie_pcm16(p_info->p_data, p_info->details.audio.size,
                                       p_info->details.audio.channel_count,
                                       p_info->details.audio.sample_rate);
    }
    return ok;
}

s32 PS4_SYSV_ABI sceAvPlayerGetStreamInfo(AvPlayerHandle handle, u32 stream_id,
                                          AvPlayerStreamInfo* p_info) {
    LOG_TRACE(Lib_AvPlayer, "stream_id = {}", stream_id);
    if (handle == nullptr || p_info == nullptr || (!AvPlayerBypassEnabled() && !IsActivePlayer(handle))) {
        return ORBIS_AVPLAYER_ERROR_INVALID_PARAMS;
    }
    if (AvPlayerBypassEnabled()) {
        std::memset(p_info, 0, sizeof(*p_info));
        p_info->type = AvPlayerStreamType::Video;
        p_info->details.video.width = 1920;
        p_info->details.video.height = 1080;
        p_info->details.video.aspect_ratio = 16.0f / 9.0f;
        return ORBIS_OK;
    }
    return handle->GetStreamInfo(stream_id, *p_info);
}

bool PS4_SYSV_ABI sceAvPlayerGetVideoData(AvPlayerHandle handle, AvPlayerFrameInfo* video_info) {
    LOG_TRACE(Lib_AvPlayer, "called");
    if (handle == nullptr || video_info == nullptr || (!AvPlayerBypassEnabled() && !IsActivePlayer(handle))) {
        return false;
    }
    if (AvPlayerBypassEnabled()) {
        return false;
    }
    return handle->GetVideoData(*video_info);
}

bool PS4_SYSV_ABI sceAvPlayerGetVideoDataEx(AvPlayerHandle handle,
                                            AvPlayerFrameInfoEx* video_info) {
    LOG_TRACE(Lib_AvPlayer, "called");
    if (handle == nullptr || video_info == nullptr || (!AvPlayerBypassEnabled() && !IsActivePlayer(handle))) {
        return false;
    }
    if (AvPlayerBypassEnabled()) {
        return false;
    }
    bool ok = handle->GetVideoData(*video_info);
    static std::atomic<u64> s_video_calls{0};
    u64 count = ++s_video_calls;
    if (count <= 5 || count % 300 == 0) {
        u64 cur_t = handle->CurrentTime();
        std::fprintf(stderr, "[AvPlayer] sceAvPlayerGetVideoDataEx(handle=%p) -> %s (frame_ts=%llu, cur_t=%llu, calls=%llu)\n",
                     (void*)handle, ok ? "OK" : "NO_DATA", ok ? (unsigned long long)video_info->timestamp : 0ULL, (unsigned long long)cur_t, (unsigned long long)count);
        std::fflush(stderr);
    }
    return ok;
}

AvPlayerHandle PS4_SYSV_ABI sceAvPlayerInit(AvPlayerInitData* data) {
    std::fprintf(stderr, "[AvPlayer] sceAvPlayerInit(data=%p)\n", (void*)data);
    std::fflush(stderr);
    LOG_TRACE(Lib_AvPlayer, "called");
    if (data == nullptr) {
        return nullptr;
    }
    if (AvPlayerBypassEnabled()) {
        auto stub = std::make_shared<StubAvPlayer>();
        stub->init_data = *data;
        auto handle = reinterpret_cast<AvPlayerHandle>(stub.get());
        {
            std::lock_guard lock(s_stub_mutex);
            s_stub_map[handle] = stub;
        }
        return handle;
    }

    if (data->memory_replacement.allocate == nullptr ||
        data->memory_replacement.allocate_texture == nullptr ||
        data->memory_replacement.deallocate == nullptr ||
        data->memory_replacement.deallocate_texture == nullptr) {
        LOG_ERROR(Lib_AvPlayer, "All allocators are required for AvPlayer Initialisation.");
        return nullptr;
    }

    AvPlayer* player = new AvPlayer(*data);
    RegisterActivePlayer(player);
    return player;
}

s32 PS4_SYSV_ABI sceAvPlayerInitEx(const AvPlayerInitDataEx* p_data, AvPlayerHandle* p_player) {
    std::fprintf(stderr, "[AvPlayer] sceAvPlayerInitEx(p_data=%p)\n", (void*)p_data);
    std::fflush(stderr);
    LOG_TRACE(Lib_AvPlayer, "called");
    if (p_data == nullptr || p_player == nullptr) {
        return ORBIS_AVPLAYER_ERROR_INVALID_PARAMS;
    }
    if (AvPlayerBypassEnabled()) {
        auto stub = std::make_shared<StubAvPlayer>();
        stub->init_data.memory_replacement = p_data->memory_replacement;
        stub->init_data.file_replacement = p_data->file_replacement;
        stub->init_data.event_replacement = p_data->event_replacement;
        stub->init_data.default_language = p_data->default_language;
        stub->init_data.num_output_video_framebuffers = p_data->num_output_video_framebuffers;
        stub->init_data.auto_start = p_data->auto_start;
        auto handle = reinterpret_cast<AvPlayerHandle>(stub.get());
        {
            std::lock_guard lock(s_stub_mutex);
            s_stub_map[handle] = stub;
        }
        *p_player = handle;
        return ORBIS_OK;
    }

    if (p_data->memory_replacement.allocate == nullptr ||
        p_data->memory_replacement.allocate_texture == nullptr ||
        p_data->memory_replacement.deallocate == nullptr ||
        p_data->memory_replacement.deallocate_texture == nullptr) {
        LOG_ERROR(Lib_AvPlayer, "All allocators are required for AvPlayer Initialisation.");
        return ORBIS_AVPLAYER_ERROR_INVALID_PARAMS;
    }

    AvPlayerInitData data = {};
    data.memory_replacement = p_data->memory_replacement;
    data.file_replacement = p_data->file_replacement;
    data.event_replacement = p_data->event_replacement;
    data.default_language = p_data->default_language;
    data.num_output_video_framebuffers = p_data->num_output_video_framebuffers;
    data.auto_start = p_data->auto_start;

    *p_player = new AvPlayer(data);
    RegisterActivePlayer(*p_player);
    return ORBIS_OK;
}

bool PS4_SYSV_ABI sceAvPlayerIsActive(AvPlayerHandle handle) {
    LOG_TRACE(Lib_AvPlayer, "called");
    if (handle == nullptr || (!AvPlayerBypassEnabled() && !IsActivePlayer(handle))) {
        return false;
    }
    if (AvPlayerBypassEnabled()) {
        return false;
    }
    bool active = handle->IsActive();
    static std::atomic<u64> s_active_calls{0};
    u64 count = ++s_active_calls;
    if (count <= 3 || count % 300 == 0) {
        std::fprintf(stderr, "[AvPlayer] sceAvPlayerIsActive(handle=%p) -> %s (calls=%llu)\n",
                     (void*)handle, active ? "ACTIVE" : "INACTIVE", (unsigned long long)count);
        std::fflush(stderr);
    }
    return active;
}

s32 PS4_SYSV_ABI sceAvPlayerJumpToTime(AvPlayerHandle handle, uint64_t time) {
    LOG_ERROR(Lib_AvPlayer, "(STUBBED) called, time (msec) = {}", time);
    if (handle == nullptr || (!AvPlayerBypassEnabled() && !IsActivePlayer(handle))) {
        return ORBIS_AVPLAYER_ERROR_INVALID_PARAMS;
    }
    return ORBIS_OK;
}

s32 PS4_SYSV_ABI sceAvPlayerPause(AvPlayerHandle handle) {
    LOG_TRACE(Lib_AvPlayer, "called");
    if (handle == nullptr || (!AvPlayerBypassEnabled() && !IsActivePlayer(handle))) {
        return ORBIS_AVPLAYER_ERROR_INVALID_PARAMS;
    }
    if (AvPlayerBypassEnabled()) {
        return ORBIS_OK;
    }
    return handle->Pause();
}

s32 PS4_SYSV_ABI sceAvPlayerPostInit(AvPlayerHandle handle, AvPlayerPostInitData* data) {
    LOG_TRACE(Lib_AvPlayer, "called");
    if (handle == nullptr || data == nullptr || (!AvPlayerBypassEnabled() && !IsActivePlayer(handle))) {
        return ORBIS_AVPLAYER_ERROR_INVALID_PARAMS;
    }
    if (AvPlayerBypassEnabled()) {
        return ORBIS_OK;
    }
    return handle->PostInit(*data);
}

s32 PS4_SYSV_ABI sceAvPlayerPrintf(const char* format, ...) {
    LOG_ERROR(Lib_AvPlayer, "(STUBBED) called");
    return ORBIS_OK;
}

s32 PS4_SYSV_ABI sceAvPlayerResume(AvPlayerHandle handle) {
    LOG_TRACE(Lib_AvPlayer, "called");
    if (handle == nullptr || (!AvPlayerBypassEnabled() && !IsActivePlayer(handle))) {
        return ORBIS_AVPLAYER_ERROR_INVALID_PARAMS;
    }
    if (AvPlayerBypassEnabled()) {
        return ORBIS_OK;
    }
    return handle->Resume();
}

s32 PS4_SYSV_ABI sceAvPlayerSetAvSyncMode(AvPlayerHandle handle, AvPlayerAvSyncMode sync_mode) {
    LOG_TRACE(Lib_AvPlayer, "called");
    if (handle == nullptr || (!AvPlayerBypassEnabled() && !IsActivePlayer(handle))) {
        return ORBIS_AVPLAYER_ERROR_INVALID_PARAMS;
    }
    if (AvPlayerBypassEnabled()) {
        return ORBIS_OK;
    }
    return handle->SetAvSyncMode(sync_mode);
}

s32 PS4_SYSV_ABI sceAvPlayerSetLogCallback(AvPlayerLogCallback log_cb, void* user_data) {
    LOG_ERROR(Lib_AvPlayer, "(STUBBED) called");
    return ORBIS_OK;
}

s32 PS4_SYSV_ABI sceAvPlayerSetLooping(AvPlayerHandle handle, bool loop_flag) {
    LOG_TRACE(Lib_AvPlayer, "called, looping = {}", loop_flag);
    if (handle == nullptr || (!AvPlayerBypassEnabled() && !IsActivePlayer(handle))) {
        return ORBIS_AVPLAYER_ERROR_INVALID_PARAMS;
    }
    if (AvPlayerBypassEnabled()) {
        return ORBIS_OK;
    }
    if (!handle->SetLooping(loop_flag)) {
        return ORBIS_AVPLAYER_ERROR_OPERATION_FAILED;
    }
    return ORBIS_OK;
}

s32 PS4_SYSV_ABI sceAvPlayerSetTrickSpeed(AvPlayerHandle handle, s32 trick_speed) {
    LOG_ERROR(Lib_AvPlayer, "(STUBBED) called speed = {}", trick_speed);
    if (handle == nullptr || (!AvPlayerBypassEnabled() && !IsActivePlayer(handle))) {
        return ORBIS_AVPLAYER_ERROR_INVALID_PARAMS;
    }
    return ORBIS_OK;
}

s32 PS4_SYSV_ABI sceAvPlayerStart(AvPlayerHandle handle) {
    std::fprintf(stderr, "[AvPlayer] sceAvPlayerStart(handle=%p)\n", (void*)handle);
    std::fflush(stderr);
    LOG_TRACE(Lib_AvPlayer, "called");
    if (handle == nullptr || (!AvPlayerBypassEnabled() && !IsActivePlayer(handle))) {
        return ORBIS_AVPLAYER_ERROR_INVALID_PARAMS;
    }
    if (AvPlayerBypassEnabled()) {
        std::shared_ptr<StubAvPlayer> stub;
        {
            std::lock_guard lock(s_stub_mutex);
            auto it = s_stub_map.find(handle);
            if (it != s_stub_map.end()) {
                stub = it->second;
            }
        }
        if (stub) {
            std::thread([weak_stub = std::weak_ptr<StubAvPlayer>(stub)] {
                runtime_thread_attach_host("AvPlayerHost");
                std::this_thread::sleep_for(std::chrono::milliseconds(20));
                StubEmitEvent(weak_stub, AvPlayerEvents::StatePlay);
                std::this_thread::sleep_for(std::chrono::milliseconds(30));
                StubEmitEvent(weak_stub, AvPlayerEvents::StateStop);
            }).detach();
        }
        return ORBIS_OK;
    }
    return handle->Start();
}

s32 PS4_SYSV_ABI sceAvPlayerStop(AvPlayerHandle handle) {
    std::fprintf(stderr, "[AvPlayer] sceAvPlayerStop(handle=%p)\n", (void*)handle);
    std::fflush(stderr);
    LOG_TRACE(Lib_AvPlayer, "called");
    if (handle == nullptr || (!AvPlayerBypassEnabled() && !IsActivePlayer(handle))) {
        return ORBIS_AVPLAYER_ERROR_INVALID_PARAMS;
    }
    if (AvPlayerBypassEnabled()) {
        return ORBIS_OK;
    }
    runtime_audio_stop_movie();
    // bbport: guest code calls this and cannot unwind a C++ exception.
    try {
        return handle->Stop();
    } catch (const std::exception& error) {
        LOG_ERROR(Lib_AvPlayer, "Stop failed: {}", error.what());
        return ORBIS_AVPLAYER_ERROR_OPERATION_FAILED;
    }
}

s32 PS4_SYSV_ABI sceAvPlayerStreamCount(AvPlayerHandle handle) {
    LOG_TRACE(Lib_AvPlayer, "called");
    if (handle == nullptr || (!AvPlayerBypassEnabled() && !IsActivePlayer(handle))) {
        return ORBIS_AVPLAYER_ERROR_INVALID_PARAMS;
    }
    if (AvPlayerBypassEnabled()) {
        return 1;
    }
    return handle->GetStreamCount();
}

s32 PS4_SYSV_ABI sceAvPlayerVprintf(const char* format, va_list args) {
    LOG_ERROR(Lib_AvPlayer, "(STUBBED) called");
    return ORBIS_OK;
}

void RegisterLib(Core::Loader::SymbolsResolver* sym) {
    LIB_FUNCTION("KMcEa+rHsIo", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerAddSource);
    LIB_FUNCTION("x8uvuFOPZhU", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerAddSourceEx);
    LIB_FUNCTION("buMCiJftcfw", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerChangeStream);
    LIB_FUNCTION("NkJwDzKmIlw", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerClose);
    LIB_FUNCTION("wwM99gjFf1Y", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerCurrentTime);
    LIB_FUNCTION("BOVKAzRmuTQ", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerDisableStream);
    LIB_FUNCTION("ODJK2sn9w4A", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerEnableStream);
    LIB_FUNCTION("Wnp1OVcrZgk", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerGetAudioData);
    LIB_FUNCTION("d8FcbzfAdQw", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerGetStreamInfo);
    LIB_FUNCTION("o3+RWnHViSg", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerGetVideoData);
    LIB_FUNCTION("JdksQu8pNdQ", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerGetVideoDataEx);
    LIB_FUNCTION("aS66RI0gGgo", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerInit);
    LIB_FUNCTION("o9eWRkSL+M4", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerInitEx);
    LIB_FUNCTION("UbQoYawOsfY", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerIsActive);
    LIB_FUNCTION("XC9wM+xULz8", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerJumpToTime);
    LIB_FUNCTION("9y5v+fGN4Wk", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerPause);
    LIB_FUNCTION("HD1YKVU26-M", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerPostInit);
    // LIB_FUNCTION("agig-iDRrTE", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerPrintf);
    LIB_FUNCTION("w5moABNwnRY", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerResume);
    LIB_FUNCTION("k-q+xOxdc3E", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerSetAvSyncMode);
    LIB_FUNCTION("eBTreZ84JFY", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerSetLogCallback);
    LIB_FUNCTION("OVths0xGfho", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerSetLooping);
    LIB_FUNCTION("av8Z++94rs0", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerSetTrickSpeed);
    LIB_FUNCTION("ET4Gr-Uu07s", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerStart);
    LIB_FUNCTION("ZC17w3vB5Lo", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerStop);
    LIB_FUNCTION("hdTyRzCXQeQ", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerStreamCount);
    LIB_FUNCTION("yN7Jhuv8g24", "libSceAvPlayer", 1, "libSceAvPlayer", sceAvPlayerVprintf);
};

} // namespace Libraries::AvPlayer
