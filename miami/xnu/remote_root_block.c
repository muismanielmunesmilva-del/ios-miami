/* Experimental read-only USB-backed block device. Never accesses local disks. */
#if defined(ARM64_BOARD_CONFIG_MIAMI)
#include <sys/param.h>
#include <sys/systm.h>
#include <sys/buf.h>
#include <sys/conf.h>
#include <sys/disk.h>
#include <sys/errno.h>
#include <sys/proc.h>
#include <miscfs/devfs/devfs.h>
#include <kern/locks.h>
#include <kern/clock.h>
#include <kern/thread.h>
#include <kern/sched_prim.h>
#include "remote_root_client.h"
#include "remote_root_bounds.h"

#define ROOT_BLOCK_SECTOR 512u
#define ROOT_BLOCK_QUEUE 16u
#define ROOT_BLOCK_MAX_IO 65536u

static LCK_GRP_DECLARE(root_block_group, "miami_root_block");
static LCK_SPIN_DECLARE(root_block_lock, &root_block_group);
static struct {
	struct miami_root_client client;
	buf_t queue[ROOT_BLOCK_QUEUE];
	unsigned head, count;
	bool ready;
	int major;
	int sleep_chan;
} rb;

int miami_remote_block_start(const struct miami_root_client *client);

static void
root_block_finish(buf_t bp, int error)
{
	if (error) buf_seterror(bp, error);
	buf_biodone(bp);
}

static int
root_block_open(__unused dev_t dev, int flags, __unused int type, __unused struct proc *p)
{
	if (!rb.ready) return ENXIO;
	return (flags & FWRITE) ? EROFS : 0;
}

static int
root_block_close(__unused dev_t dev, __unused int flags, __unused int type, __unused struct proc *p)
{
	return 0;
}

static void
root_block_strategy(buf_t bp)
{
	daddr64_t sector = buf_blkno(bp);
	uint32_t count = buf_count(bp);
	uint64_t offset = 0;
	buf_setresid(bp, count);
	int validity = miami_root_block_bounds((buf_flags(bp) & B_READ) != 0,
	    sector, count, rb.client.image_size, &offset);
	if (validity == 1) { root_block_finish(bp, EROFS); return; }
	if (!rb.ready) { root_block_finish(bp, ENXIO); return; }
	if (validity != 0) { root_block_finish(bp, EINVAL); return; }
	if (count == 0) { root_block_finish(bp, 0); return; }
	lck_spin_lock(&root_block_lock);
	if (rb.count == ROOT_BLOCK_QUEUE) {
		lck_spin_unlock(&root_block_lock);
		root_block_finish(bp, EBUSY);
		return;
	}
	rb.queue[(rb.head + rb.count) % ROOT_BLOCK_QUEUE] = bp;
	rb.count++;
	lck_spin_unlock(&root_block_lock);
}

static int
root_block_ioctl(__unused dev_t dev, u_long cmd, caddr_t data,
    __unused int flags, __unused struct proc *p)
{
	switch (cmd) {
	case DKIOCGETBLOCKSIZE: *(uint32_t *)data = ROOT_BLOCK_SECTOR; return 0;
	case DKIOCGETPHYSICALBLOCKSIZE: *(uint32_t *)data = ROOT_BLOCK_SECTOR; return 0;
	case DKIOCSETBLOCKSIZE: return *(uint32_t *)data == ROOT_BLOCK_SECTOR ? 0 : EINVAL;
	case DKIOCGETBLOCKCOUNT: *(uint64_t *)data = rb.client.image_size / ROOT_BLOCK_SECTOR; return 0;
	case DKIOCISWRITABLE: *(uint32_t *)data = 0; return 0;
	case DKIOCGETMAXBLOCKCOUNTREAD: *(uint64_t *)data = ROOT_BLOCK_MAX_IO / ROOT_BLOCK_SECTOR; return 0;
	case DKIOCGETMAXBLOCKCOUNTWRITE: *(uint64_t *)data = 0; return 0;
	default: return ENOTTY;
	}
}

static int root_block_psize(__unused dev_t dev)
{
	return rb.ready ? (int)MIN(rb.client.image_size / ROOT_BLOCK_SECTOR, INT_MAX) : -1;
}

static const struct bdevsw root_block_bdevsw = {
	.d_open = root_block_open, .d_close = root_block_close,
	.d_strategy = root_block_strategy, .d_ioctl = root_block_ioctl,
	.d_dump = eno_dump, .d_psize = root_block_psize, .d_type = D_DISK,
};

static void
root_block_worker(void *arg __unused, wait_result_t wr __unused)
{
	for (;;) {
		buf_t bp = NULL;
		lck_spin_lock(&root_block_lock);
		if (rb.count) {
			bp = rb.queue[rb.head];
			rb.head = (rb.head + 1) % ROOT_BLOCK_QUEUE;
			rb.count--;
		}
		lck_spin_unlock(&root_block_lock);
		if (bp == NULL) {
			uint64_t deadline;
			clock_interval_to_deadline(10, NSEC_PER_MSEC, &deadline);
			(void)assert_wait_deadline(&rb.sleep_chan, THREAD_UNINT, deadline);
			thread_block(THREAD_CONTINUE_NULL);
			continue;
		}
		caddr_t addr = (caddr_t)buf_dataptr(bp);
		bool mapped = false;
		int error = 0;
		if (addr == NULL) { error = buf_map(bp, &addr); mapped = error == 0; }
		if (!error && addr == NULL) error = EIO;
		if (!error && miami_root_read(&rb.client,
		    (uint64_t)buf_blkno(bp) * ROOT_BLOCK_SECTOR,
		    (uint8_t *)addr, buf_count(bp)) != 0) error = EIO;
		if (mapped) (void)buf_unmap(bp);
		if (!error) buf_setresid(bp, 0);
		root_block_finish(bp, error);
	}
}

static void
root_block_test(void *arg __unused, wait_result_t wr __unused)
{
	static uint8_t data[4096];
	buf_t bp = buf_alloc(NULL);
	if (!bp) { printf("MIAMI ROOT BLOCK: buffer allocation failed\n"); return; }
	buf_setdataptr(bp, (uintptr_t)data);
	buf_setcount(bp, sizeof(data));
	buf_setblkno(bp, 0);
	buf_setflags(bp, B_READ);
	root_block_bdevsw.d_strategy(bp);
	int error = buf_biowait(bp);
	if (!error && buf_resid(bp) == 0 && data[1024] == 'H' &&
	    (data[1025] == '+' || data[1025] == 'X'))
		printf("MIAMI ROOT BLOCK: 4096-byte strategy HFS read verified\n");
	else printf("MIAMI ROOT BLOCK: strategy read failed error=%d resid=%u\n", error, buf_resid(bp));
	buf_free(bp);
	if (root_block_open(makedev(rb.major, 0), FWRITE, 0, NULL) == EROFS)
		printf("MIAMI ROOT BLOCK: write open rejected\n");
	else printf("MIAMI ROOT BLOCK: write rejection failed\n");
}

/* Caller transfers exclusive use of the connected transport on success. */
int
miami_remote_block_start(const struct miami_root_client *client)
{
	thread_t worker, test;
	if (!client || client->image_size < 4096 || (client->image_size % ROOT_BLOCK_SECTOR)) return EINVAL;
	rb.client = *client;
	rb.major = bdevsw_add(-1, &root_block_bdevsw);
	if (rb.major < 0) return ENXIO;
	void *node = devfs_make_node(makedev(rb.major, 0), DEVFS_BLOCK,
	    UID_ROOT, GID_OPERATOR, 0440, "miamiusbroot0");
	if (!node) { bdevsw_remove(rb.major, &root_block_bdevsw); return ENXIO; }
	if (kernel_thread_start(root_block_worker, NULL, &worker) != KERN_SUCCESS) {
		devfs_remove(node); bdevsw_remove(rb.major, &root_block_bdevsw); return ENOMEM;
	}
	thread_deallocate(worker);
	rb.ready = true;
	printf("MIAMI ROOT BLOCK: read-only miamiusbroot0 registered\n");
	if (kernel_thread_start(root_block_test, NULL, &test) == KERN_SUCCESS) thread_deallocate(test);
	else printf("MIAMI ROOT BLOCK: could not start strategy test\n");
	return 0;
}
#endif
