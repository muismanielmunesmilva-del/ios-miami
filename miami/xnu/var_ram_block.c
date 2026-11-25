/*
 * Experimental writable RAM disk for /private/var in the rootpid1 bring-up.
 * Kernel memory only, initialised from a generated HFS+ template
 * (miami/userspace/var_template.py); nothing is written to any local disk and
 * nothing persists across a reboot. init mounts it read-write on the remote
 * root's /private/var before the chroot into that root.
 */
#if defined(ARM64_BOARD_CONFIG_MIAMI)
#include <sys/param.h>
#include <sys/systm.h>
#include <sys/buf.h>
#include <sys/conf.h>
#include <sys/disk.h>
#include <sys/errno.h>
#include <sys/proc.h>
#include <miscfs/devfs/devfs.h>
#include <kern/kalloc.h>
#include "var_template.h"

#define VAR_SECTOR 512u
#define VAR_MAX_IO (1024u * 1024u)

static struct {
	uint8_t *base;
	int major;
	bool ready;
	bool error_reported;
} vb;

int miami_var_block_start(void);

static int
var_block_open(__unused dev_t dev, __unused int flags, __unused int type, __unused struct proc *p)
{
	return vb.ready ? 0 : ENXIO;
}

static int
var_block_close(__unused dev_t dev, __unused int flags, __unused int type, __unused struct proc *p)
{
	return 0;
}

static void
var_block_strategy(buf_t bp)
{
	daddr64_t sector = buf_blkno(bp);
	uint32_t count = buf_count(bp);
	uint64_t offset = (uint64_t)sector * VAR_SECTOR;
	caddr_t addr = NULL;
	int error = 0;

	buf_setresid(bp, count);
	if (!vb.ready) {
		error = ENXIO;
	} else if (sector < 0 || offset > MIAMI_VAR_IMAGE_BYTES || count > MIAMI_VAR_IMAGE_BYTES - offset) {
		error = EINVAL;
	} else if (count != 0) {
		error = buf_map(bp, &addr);
		if (error == 0) {
			if (addr == NULL) {
				error = EIO;
			} else if (buf_flags(bp) & B_READ) {
				memcpy(addr, vb.base + offset, count);
			} else {
				memcpy(vb.base + offset, addr, count);
			}
			(void)buf_unmap(bp);
		}
	}
	if (error == 0) {
		buf_setresid(bp, 0);
	} else {
		if (!vb.error_reported) {
			vb.error_reported = true;
			printf("MIAMI VAR: I/O error %d sector=%lld bytes=%u\n", error, (long long)sector, count);
		}
		buf_seterror(bp, error);
	}
	buf_biodone(bp);
}

static int
var_block_ioctl(__unused dev_t dev, u_long cmd, caddr_t data,
    __unused int flags, __unused struct proc *p)
{
	switch (cmd) {
	case DKIOCGETBLOCKSIZE: *(uint32_t *)data = VAR_SECTOR; return 0;
	case DKIOCGETPHYSICALBLOCKSIZE: *(uint32_t *)data = VAR_SECTOR; return 0;
	case DKIOCSETBLOCKSIZE: return *(uint32_t *)data == VAR_SECTOR ? 0 : EINVAL;
	case DKIOCGETBLOCKCOUNT: *(uint64_t *)data = MIAMI_VAR_IMAGE_BYTES / VAR_SECTOR; return 0;
	case DKIOCISWRITABLE: *(uint32_t *)data = 1; return 0;
	case DKIOCGETMAXBLOCKCOUNTREAD: *(uint64_t *)data = VAR_MAX_IO / VAR_SECTOR; return 0;
	case DKIOCGETMAXBLOCKCOUNTWRITE: *(uint64_t *)data = VAR_MAX_IO / VAR_SECTOR; return 0;
	case DKIOCGETFEATURES: *(uint32_t *)data = 0; return 0;
	case DKIOCSYNCHRONIZE: return 0;               /* RAM: nothing to flush */
	case DKIOCSYNCHRONIZECACHE: return 0;
	default: return ENOTTY;
	}
}

static int
var_block_psize(__unused dev_t dev)
{
	return vb.ready ? (int)(MIAMI_VAR_IMAGE_BYTES / VAR_SECTOR) : -1;
}

static const struct bdevsw var_block_bdevsw = {
	.d_open = var_block_open, .d_close = var_block_close,
	.d_strategy = var_block_strategy, .d_ioctl = var_block_ioctl,
	.d_dump = eno_dump, .d_psize = var_block_psize, .d_type = D_DISK,
};

int
miami_var_block_start(void)
{
	size_t used = 0;

	if (vb.ready) return 0;
	vb.base = kalloc_data(MIAMI_VAR_IMAGE_BYTES, Z_WAITOK | Z_ZERO);
	if (vb.base == NULL) {
		printf("MIAMI VAR: cannot allocate %u MiB\n", MIAMI_VAR_IMAGE_BYTES >> 20);
		return ENOMEM;
	}
	for (unsigned i = 0; i < MIAMI_VAR_RUNS; i++) {
		size_t off = (size_t)miami_var_runs[i][0] * MIAMI_VAR_BLOCK;
		size_t len = (size_t)miami_var_runs[i][1] * MIAMI_VAR_BLOCK;
		if (off > MIAMI_VAR_IMAGE_BYTES || len > MIAMI_VAR_IMAGE_BYTES - off ||
		    len > sizeof(miami_var_data) - used) {
			goto bad_template;
		}
		memcpy(vb.base + off, miami_var_data + used, len);
		used += len;
	}
	if (used != sizeof(miami_var_data) || vb.base[1024] != 'H' ||
	    (vb.base[1025] != 'X' && vb.base[1025] != '+')) {
		goto bad_template;
	}
	vb.major = bdevsw_add(-1, &var_block_bdevsw);
	if (vb.major < 0) goto fail;
	vb.ready = true;
	if (devfs_make_node(makedev(vb.major, 0), DEVFS_BLOCK,
	    UID_ROOT, GID_OPERATOR, 0640, "miamivar0") == NULL) {
		vb.ready = false;
		bdevsw_remove(vb.major, &var_block_bdevsw);
		goto fail;
	}
	printf("MIAMI VAR: writable RAM /dev/miamivar0 registered (%u MiB, %u template runs)\n",
	    MIAMI_VAR_IMAGE_BYTES >> 20, MIAMI_VAR_RUNS);
	return 0;
bad_template:
	printf("MIAMI VAR: template invalid\n");
fail:
	kfree_data(vb.base, MIAMI_VAR_IMAGE_BYTES);
	vb.base = NULL;
	return ENXIO;
}
#endif
