// engine: host threads that may call guest code (AvPlayer allocator callbacks).
// Each thread gets a guest TCB (GS base, TLS) from the C runtime before running.
#pragma once
#include <atomic>
#include <chrono>
#include <cstdio>
#include <functional>
#include <memory>
#include <stop_token>
#include <system_error>
#include <thread>
#include "common/types.h"

extern "C" void runtime_thread_attach_host(const char* name);



namespace Libraries::Kernel {
class Thread {
public:
    Thread() = default;
    ~Thread() { Stop(); }
    void Run(std::function<void(std::stop_token)>&& func, const char* thread_name = "bb:hle") {
        finished = std::make_shared<std::atomic<bool>>(false);
        native_tid = std::make_shared<std::atomic<uint32_t>>(0);
        name = thread_name ? thread_name : "bb:hle";
        thread = std::jthread([func = std::move(func), done = finished, ptid = native_tid, tname = name](std::stop_token stop) {
#ifdef _WIN32
            if (ptid) ptid->store((uint32_t)GetCurrentThreadId());
#endif
            runtime_thread_attach_host(tname);
            func(stop);
            done->store(true);
        });
    }
    // A thread may stop its own Thread object (AvPlayer does); it detaches instead of joining.
    // engine: these are called from guest code, which a C++ exception cannot unwind: a failed
    // join is logged and the thread detached instead.
    void Join() {
        if (!thread.joinable()) return;
        uint32_t caller_tid = 0;
#ifdef _WIN32
        caller_tid = (uint32_t)GetCurrentThreadId();
#endif
        uint32_t target_tid = native_tid ? native_tid->load() : 0;
        std::fprintf(stderr, "[HLE thread] Joining '%s' (target_tid=%u) from caller_tid=%u (finished=%d)\n",
                     name ? name : "unnamed", target_tid, caller_tid, finished ? finished->load() : -1);
        std::fflush(stderr);
        try {
            if (thread.get_id() == std::this_thread::get_id()) {
                std::fprintf(stderr, "[HLE thread] Detaching self '%s'\n", name ? name : "unnamed");
                thread.detach();
            } else {
                thread.join();
                std::fprintf(stderr, "[HLE thread] Joined '%s' successfully\n", name ? name : "unnamed");
            }
        } catch (const std::system_error& error) {
            // Windows (libc++ on Win32 threads): the join can fail although the thread is fine.
            // Wait for its function to return, so nothing it uses is freed under it, then let go.
            std::fprintf(stderr, "HLE thread: join failed (%s); waiting for it to finish\n", error.what());
            if (thread.get_id() != std::this_thread::get_id()) {
                for (int waited = 0; finished && !finished->load() && waited < 5000; ++waited) {
                    std::this_thread::sleep_for(std::chrono::milliseconds(1));
                }
            }
            if (thread.joinable()) thread.detach();
        }
        std::fflush(stderr);
    }
    bool Joinable() const { return thread.joinable(); }
    uint32_t GetTid() const { return native_tid ? native_tid->load() : 0; }
    bool IsFinished() const { return finished ? finished->load() : true; }
    const char* GetName() const { return name; }
    void Stop() {
        if (thread.joinable()) {
            thread.request_stop();
            Join();
        }
    }

private:
    std::jthread thread;
    std::shared_ptr<std::atomic<bool>> finished;
    std::shared_ptr<std::atomic<uint32_t>> native_tid;
    const char* name = nullptr;
};
} // namespace Libraries::Kernel
