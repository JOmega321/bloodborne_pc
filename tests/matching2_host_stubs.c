/* SPDX-License-Identifier: GPL-2.0-or-later
 * Headless ABI fixture for libbbgpu's unrelated game/renderer host imports. Networking,
 * packet framing, crypto, signaling and shadNet are the actual production module.
 * No mapped game memory is provided; this harness never initializes the renderer.
 */
#include <stdlib.h>
#include <stdint.h>
uintptr_t runtime_memory_set_note_write_hook(void) {return 0;}
uintptr_t runtime_memory_direct_phys(void) {return 0;}
uintptr_t runtime_pad_mouse_look(void) {return 0;}
uintptr_t runtime_restarting(void) {return 0;}
uintptr_t runtime_memory_resolve(void) {return 0;}
uintptr_t runtime_tsc_frequency(void) {return 3000000000ull;}
uintptr_t runtime_wait_report(void) {return 0;}
uintptr_t runtime_memory_gpu_protect(void) {return 0;}
uintptr_t runtime_memory_decommit(void) {return 0;}
uintptr_t runtime_extra_direct_map(void) {return 0;}
uintptr_t runtime_memory_set_grow(void) {return 0;}
uintptr_t runtime_pad_prompt_generation(void) {return 0;}
uintptr_t runtime_memory_deferred(void) {return 0;}
uintptr_t runtime_savedata_active_slot(void) {return 0;}
uintptr_t runtime_memory_is_mapped(void) {return 0;}
uintptr_t runtime_memory_trap_reasons(void) {return 0;}
uintptr_t runtime_memory_set_guest_chunk_private(void) {return 0;}
uintptr_t runtime_pad_prompt_device(void) {return 0;}
uintptr_t runtime_memory_commit_ahead(void) {return 0;}
uintptr_t runtime_memory_set_cpu_write_hook(void) {return 0;}
uintptr_t runtime_thread_attach_host(void) {return 0;}
uintptr_t runtime_memory_trap_stats(void) {return 0;}
uintptr_t runtime_re_watch(void) {return 0;}
uintptr_t runtime_process_time_counter(void) {return 0;}
uintptr_t runtime_sleep_stats(void) {return 0;}
uintptr_t runtime_low_map(void) {return 0;}
uintptr_t runtime_disabled_optimizations(void) {return 0;}
uintptr_t runtime_file_translate(void) {return 0;}
uintptr_t runtime_memory_note_write(void) {return 0;}
uintptr_t runtime_memory_pool_fd(void) {return 0;}
uintptr_t runtime_memory_set_guest_lazy(void) {return 0;}
uintptr_t runtime_memory_set_guest_chunk_whole(void) {return 0;}
uintptr_t runtime_restart(void) {return 0;}
uintptr_t runtime_memory_commit(void) {return 0;}
uintptr_t runtime_memory_vma_info(void) {return 0;}
uintptr_t runtime_memory_clamp(void) {return 0;}
uintptr_t runtime_memory_set_gpu_hooks(void) {return 0;}
uintptr_t runtime_memory_region(void) {return 0;}
uintptr_t runtime_memory_trap(void) {return 0;}
uintptr_t runtime_memory_set_guest_chunk_free(void) {return 0;}
uintptr_t runtime_file_host_path(void) {return 0;}
__thread uintptr_t runtime_fault_recover;
uintptr_t runtime_errno(void) {return 0;}
uintptr_t runtime_memory_read_backing(void) {return 0;}
uintptr_t runtime_memory_set_host_only_allocations(void) {return 0;}
uintptr_t runtime_memory_discard_direct(void) {return 0;}
uintptr_t runtime_memory_set_write_watch(void) {return 0;}
uintptr_t runtime_memory_note_pinned(void) {return 0;}
uintptr_t runtime_experiment_bits(void) {return 0;}
uintptr_t runtime_pad_steam_only(void) {return 0;}
uintptr_t runtime_memory_generation(void) {return 0;}
uintptr_t runtime_memory_backing_pointer(void) {return 0;}
uintptr_t runtime_heap_growths(void) {return 0;}
uintptr_t runtime_pad_prompt(void) {return 0;}
uintptr_t runtime_memory_set_guest_chunk_allocator(void) {return 0;}
uintptr_t runtime_memory_write_backing(void) {return 0;}
uintptr_t runtime_process_time_us(void) {return 0;}
const char *runtime_file_user_dir(void) {return getenv("BB_DATA_DIR");}
uintptr_t runtime_memory_low_info(void) {return 0;}
