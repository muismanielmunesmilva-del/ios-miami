/*
 * MIAMI Hardware Touchscreen Driver (Goodix GT9916S on QUP GENI SPI0).
 *
 * Motorola Edge 30 Neo (XT2245-1 / SM6375 holi / Blair):
 * - SPI Engine: QUPv3 Wrapper 0, Serial Engine 0 (GENI SPI) at 0x04a80000 (0x4000)
 * - Clock Controller (GCC): 0x01400000 (0x1f0000)
 *     GCC vote register: 0x52008 (APCS clock sleep/enable vote)
 *     QUP0 Core / SE0 clock: BIT(22) = gcc_qupv3_wrap0_s0_clk
 *     QUP0 M-AHB clock:      BIT(20) = gcc_qupv3_wrap_0_m_ahb_clk
 *     QUP0 S-AHB clock:      BIT(21) = gcc_qupv3_wrap_0_s_ahb_clk (or 0x7900c)
 *     SE0 RCG:               0x21148 (cmd_rcgr)
 * - TLMM Pin Controller: 0x00400000 (0x800000)
 *     GPIO 0: MOSI (qup00, mux 1)
 *     GPIO 1: MISO (qup00, mux 1)
 *     GPIO 2: CS_N (qup00, mux 1 or GPIO output)
 *     GPIO 3: CLK  (qup00, mux 1)
 *     GPIO 21: RESET_N (active low, GPIO output, default HIGH)
 *     GPIO 22: INT_N   (active low, GPIO input, pull up)
 * - Touch Digitizer: Goodix GT9916S
 *     SPI framing: 8-bit, Mode 0 (CPOL=0, CPHA=0), MSB first, 4-byte FIFO packing
 *     Read command: 0xF1, 32-bit addr BE, 3 dummy bytes (0xFF, 0xFF, 0xFF)
 *     Write command: 0xF0, 32-bit addr BE, data...
 *     Touch report addr: Goodix Berlin protocol (0x10014 version, 0x10070 IC info)
 *     ACK register: 0x00 written to status byte at touch_address
 *
 * Dispatches coordinates directly to MiamiHIDTouch subsystem (miami_hid_touch).
 */
#if defined(ARM64_BOARD_CONFIG_MIAMI)
#include <sys/param.h>
#include <sys/systm.h>
#include <sys/errno.h>
#include <kern/clock.h>
#include <kern/thread.h>
#include <kern/sched_prim.h>
#include <machine/machine_routines.h>
#include <pexpert/pexpert.h>

extern vm_offset_t ml_io_map(vm_offset_t, vm_size_t);
extern void miami_hid_touch(int finger, int down, int x, int y);
void miami_touch_init(void);

#define TOUCH_SE_PA          0x04a80000u
#define TOUCH_GCC_PA         0x01400000u
#define TOUCH_TLMM_PA        0x00400000u

#define TOUCH_GCC_VOTE       0x52008u
#define TOUCH_RCG_CMD        0x21148u
#define TOUCH_RCG_CFG        (TOUCH_RCG_CMD + 4u)

#define TLMM_GPIO_CFG(n)     ((uint32_t)(n) * 0x1000u)
#define TLMM_GPIO_IO(n)      (TLMM_GPIO_CFG(n) + 4u)

/* TLMM GPIO pins */
#define PIN_MOSI             0u
#define PIN_MISO             1u
#define PIN_CS               2u
#define PIN_CLK              3u
#define PIN_RESET            21u
#define PIN_INT              22u

/* GENI SE registers */
#define GENI_FORCE_DEFAULT   0x020u
#define GENI_OUTPUT_CTRL     0x024u
#define GENI_CGC_CTRL        0x028u
#define GENI_STATUS          0x040u
#define GENI_SER_M_CLK_CFG   0x048u
#define GENI_IF_DISABLE_RO   0x064u
#define GENI_FW_REVISION_RO  0x068u
#define GENI_CLK_SEL         0x07cu
#define SPI_CPHA             0x224u
#define SPI_LOOPBACK         0x22cu
#define SPI_CPOL             0x230u
#define SPI_DEMUX_OUTPUT_INV 0x24cu
#define SPI_DEMUX_SEL        0x250u
#define GENI_BYTE_GRAN       0x254u
#define GENI_DMA_MODE_EN     0x258u
#define SPI_TRANS_CFG        0x25cu
#define GENI_TX_PACKING_CFG0 0x260u
#define GENI_TX_PACKING_CFG1 0x264u
#define SPI_WORD_LEN         0x268u
#define SPI_TX_TRANS_LEN     0x26cu
#define SPI_RX_TRANS_LEN     0x270u
#define SPI_DELAY_COUNTERS   0x278u
#define GENI_RX_PACKING_CFG0 0x284u
#define GENI_RX_PACKING_CFG1 0x288u
#define GENI_M_CMD0          0x600u
#define GENI_M_CMD_CTRL      0x604u
#define GENI_M_IRQ_STATUS    0x610u
#define GENI_M_IRQ_EN        0x614u
#define GENI_M_IRQ_CLEAR     0x618u
#define GENI_S_IRQ_CLEAR     0x648u
#define GENI_TX_FIFO         0x700u
#define GENI_RX_FIFO         0x780u
#define GENI_TX_FIFO_STATUS  0x800u
#define GENI_RX_FIFO_STATUS  0x804u
#define GENI_TX_WATERMARK    0x80cu
#define GENI_RX_WATERMARK    0x810u
#define GENI_RX_RFR_WATERMARK 0x814u
#define SE_HW_PARAM_0        0xe24u
#define SE_DMA_GENERAL_CFG   0xe30u

#define M_CMD_DONE           (1u << 0)
#define M_CMD_CANCEL         (1u << 4)
#define M_CMD_ABORT          (1u << 5)
#define M_ERRORS             ((1u << 1) | (1u << 2) | (1u << 3) | (1u << 24) | (1u << 25) | (1u << 28) | (1u << 29))
#define SPI_FULL_DUPLEX      (3u << 27)

/* Goodix Berlin protocol registers */
#define GOODIX_FW_VERSION    0x10014u
#define GOODIX_IC_INFO       0x10070u
#define GOODIX_MAX_READ      512u
#define GOODIX_MAX_TOUCHES   10u
#define GOODIX_STATUS_TOUCH  0x80u
#define GOODIX_STATUS_REQUEST 0x40u

static vm_offset_t touch_se, touch_gcc, touch_tlmm;
static bool touch_started;
static uint32_t touch_fifo_depth = 16;
static uint32_t touch_report_addr = 0;
static uint32_t touch_max_x = 1080;
static uint32_t touch_max_y = 2400;
static int touch_sleep_chan;

struct touch_point {
	bool down;
	int x;
	int y;
};
static struct touch_point touch_state[GOODIX_MAX_TOUCHES];

static inline uint32_t
touch_rd(vm_offset_t base, uint32_t off)
{
	uint32_t v = *(volatile uint32_t *)(base + off);
	__asm__ volatile("dmb oshld" ::: "memory");
	return v;
}

static inline void
touch_wr(vm_offset_t base, uint32_t off, uint32_t val)
{
	__asm__ volatile("dmb oshst" ::: "memory");
	*(volatile uint32_t *)(base + off) = val;
	__asm__ volatile("dsb osh" ::: "memory");
}

static void
touch_wait(unsigned ms)
{
	uint64_t deadline;
	clock_interval_to_deadline(ms, NSEC_PER_MSEC, &deadline);
	(void)assert_wait_deadline(&touch_sleep_chan, THREAD_UNINT, deadline);
	thread_block(THREAD_CONTINUE_NULL);
}

static void
touch_gpio_cfg(unsigned pin, unsigned mux, unsigned pull, unsigned drive, bool out)
{
	uint32_t off = TLMM_GPIO_CFG(pin);
	uint32_t cfg = touch_rd(touch_tlmm, off);
	if (out) {
		touch_wr(touch_tlmm, TLMM_GPIO_IO(pin),
		    touch_rd(touch_tlmm, TLMM_GPIO_IO(pin)) | 2u);
	}
	cfg &= ~0x3ffu;
	cfg |= (mux << 2) | pull | (drive << 6) | (out ? 0x200u : 0u);
	touch_wr(touch_tlmm, off, cfg);
}

static void
touch_gpio_set(unsigned pin, bool high)
{
	touch_wr(touch_tlmm, TLMM_GPIO_IO(pin), high ? 2u : 0u);
}

static bool
touch_gpio_get(unsigned pin)
{
	return (touch_rd(touch_tlmm, TLMM_GPIO_IO(pin)) & 1u) != 0;
}

static bool
touch_clocks_init(void)
{
	/*
	 * Vote for QUPv3 wrapper 0 core, M-AHB and S-AHB in GCC.
	 * BIT(22): gcc_qupv3_wrap0_s0_clk
	 * BIT(20): gcc_qupv3_wrap_0_m_ahb_clk
	 * BIT(21): gcc_qupv3_wrap_0_s_ahb_clk
	 */
	uint32_t vote_mask = (1u << 22) | (1u << 20) | (1u << 21);
	uint32_t v = touch_rd(touch_gcc, TOUCH_GCC_VOTE);
	touch_wr(touch_gcc, TOUCH_GCC_VOTE, v | vote_mask);

	/* Check RCG configuration */
	uint32_t rcg_cmd = touch_rd(touch_gcc, TOUCH_RCG_CMD);
	uint32_t rcg_cfg = touch_rd(touch_gcc, TOUCH_RCG_CFG);
	printf("MIAMI TOUCH: gcc vote=%#x rcg_cmd=%#x rcg_cfg=%#x\n",
	    touch_rd(touch_gcc, TOUCH_GCC_VOTE), rcg_cmd, rcg_cfg);

	return true;
}

static void
touch_pins_init(void)
{
	/* SPI pins: GPIO 0 (MOSI), 1 (MISO), 2 (CS), 3 (CLK) -> mux 1 (qup00) */
	touch_gpio_cfg(PIN_MOSI, 1, 0, 3, false);
	touch_gpio_cfg(PIN_MISO, 1, 0, 3, false);
	touch_gpio_cfg(PIN_CS,   1, 0, 3, false);
	touch_gpio_cfg(PIN_CLK,  1, 0, 3, false);

	/* Reset pin: GPIO 21 (GPIO output, start High) */
	touch_gpio_cfg(PIN_RESET, 0, 0, 2, true);
	touch_gpio_set(PIN_RESET, true);

	/* Interrupt pin: GPIO 22 (GPIO input, pull up) */
	touch_gpio_cfg(PIN_INT, 0, 3, 0, false);
}

static void
geni_recover(void)
{
	touch_wr(touch_se, GENI_M_CMD_CTRL, 1u << 2); /* cancel */
	for (int i = 0; i < 2000 && !(touch_rd(touch_se, GENI_M_IRQ_STATUS) & M_CMD_CANCEL); i++) {
		delay(10);
	}
	if (!(touch_rd(touch_se, GENI_M_IRQ_STATUS) & M_CMD_CANCEL)) {
		touch_wr(touch_se, GENI_M_CMD_CTRL, 1u << 1); /* abort */
		for (int i = 0; i < 2000 && !(touch_rd(touch_se, GENI_M_IRQ_STATUS) & M_CMD_ABORT); i++) {
			delay(10);
		}
	}
	for (int i = 0; i < 64 && (touch_rd(touch_se, GENI_RX_FIFO_STATUS) & 0x01ffffffu); i++) {
		(void)touch_rd(touch_se, GENI_RX_FIFO);
	}
	touch_wr(touch_se, GENI_M_IRQ_CLEAR, 0xffffffffu);
}

static void
geni_drain(uint8_t *rx, uint32_t length, uint32_t *received)
{
	uint32_t status = touch_rd(touch_se, GENI_RX_FIFO_STATUS);
	uint32_t words = status & 0x01ffffffu;
	uint32_t bytes = words * 4u;

	if (status & 0x80000000u) {
		uint32_t valid = (status >> 28) & 7u;
		if (valid && valid < 4u) {
			bytes -= (4u - valid);
		}
	}
	for (uint32_t i = 0; i < words; i++) {
		uint32_t word = touch_rd(touch_se, GENI_RX_FIFO);
		for (int j = 0; j < 4 && bytes; j++, bytes--) {
			if (*received < length) {
				if (rx) {
					rx[*received] = (uint8_t)(word >> (8 * j));
				}
				(*received)++;
			}
		}
	}
}

static bool
geni_spi_init(void)
{
	uint32_t fw_rev = touch_rd(touch_se, GENI_FW_REVISION_RO);
	uint32_t if_dis = touch_rd(touch_se, GENI_IF_DISABLE_RO);
	printf("MIAMI TOUCH: GENI fw_rev=%#x if_dis=%#x\n", fw_rev, if_dis);

	if ((fw_rev >> 8 & 0xffu) != 1u) {
		printf("MIAMI TOUCH: not SPI firmware protocol (%#x)\n", fw_rev);
		return false;
	}
	if (if_dis & 1u) {
		printf("MIAMI TOUCH: FIFO interface disabled\n");
		return false;
	}
	touch_fifo_depth = (touch_rd(touch_se, SE_HW_PARAM_0) >> 16) & 0x3fu;
	if (touch_fifo_depth < 4) {
		touch_fifo_depth = 16;
	}
	printf("MIAMI TOUCH: FIFO depth=%u\n", touch_fifo_depth);

	touch_wr(touch_se, GENI_M_IRQ_CLEAR, 0xffffffffu);
	touch_wr(touch_se, GENI_S_IRQ_CLEAR, 0xffffffffu);
	touch_wr(touch_se, GENI_CGC_CTRL, touch_rd(touch_se, GENI_CGC_CTRL) | 0x7fu);
	touch_wr(touch_se, SE_DMA_GENERAL_CFG, touch_rd(touch_se, SE_DMA_GENERAL_CFG) | 0xfu);
	touch_wr(touch_se, GENI_OUTPUT_CTRL, 0x7fu);
	touch_wr(touch_se, GENI_FORCE_DEFAULT, 1u);
	touch_wr(touch_se, GENI_DMA_MODE_EN, touch_rd(touch_se, GENI_DMA_MODE_EN) & ~1u);
	touch_wr(touch_se, GENI_RX_WATERMARK, touch_fifo_depth - 3u);
	touch_wr(touch_se, GENI_RX_RFR_WATERMARK, touch_fifo_depth - 2u);
	touch_wr(touch_se, GENI_TX_WATERMARK, 0u);
	touch_wr(touch_se, GENI_M_IRQ_EN, touch_rd(touch_se, GENI_M_IRQ_EN) | 0x7fc0007fu);

	/* Mode 0, CS 0, 8-bit words, MSB first, 4 bytes per FIFO word */
	touch_wr(touch_se, SPI_LOOPBACK, 0u);
	touch_wr(touch_se, SPI_DEMUX_SEL, 0u);
	touch_wr(touch_se, SPI_CPHA, 0u);
	touch_wr(touch_se, SPI_CPOL, 0u);
	touch_wr(touch_se, SPI_DEMUX_OUTPUT_INV, 0u);
	touch_wr(touch_se, SPI_TRANS_CFG, touch_rd(touch_se, SPI_TRANS_CFG) & ~2u);
	touch_wr(touch_se, SPI_DELAY_COUNTERS, 0u);
	touch_wr(touch_se, GENI_TX_PACKING_CFG0, 0x0007f8feu);
	touch_wr(touch_se, GENI_TX_PACKING_CFG1, 0x000ffefeu);
	touch_wr(touch_se, GENI_RX_PACKING_CFG0, 0x0007f8feu);
	touch_wr(touch_se, GENI_RX_PACKING_CFG1, 0x000ffefeu);
	touch_wr(touch_se, GENI_BYTE_GRAN, 0u);
	touch_wr(touch_se, SPI_WORD_LEN, 8u - 4u);

	/* Clock divider: 19.2 MHz / 2 = 9.6 MHz or / 4 = 4.8 MHz */
	touch_wr(touch_se, GENI_CLK_SEL, 0u);
	touch_wr(touch_se, GENI_SER_M_CLK_CFG, (2u << 4) | 1u);

	return true;
}

static bool
geni_transfer(const uint8_t *tx, uint8_t *rx, uint32_t length)
{
	uint32_t sent = 0, received = 0, status = 0;
	uint64_t deadline;

	for (int i = 0; touch_rd(touch_se, GENI_STATUS) & 1u; i++) {
		if (i > 2000) {
			geni_recover();
			break;
		}
		delay(10);
	}
	touch_wr(touch_se, GENI_M_IRQ_CLEAR, 0xffffffffu);
	touch_wr(touch_se, SPI_TX_TRANS_LEN, length);
	touch_wr(touch_se, SPI_RX_TRANS_LEN, length);
	touch_wr(touch_se, GENI_M_CMD0, SPI_FULL_DUPLEX);

	clock_interval_to_deadline(100, NSEC_PER_MSEC, &deadline);
	while (mach_absolute_time() < deadline) {
		while (sent < length && (touch_rd(touch_se, GENI_TX_FIFO_STATUS) & 0x0fffffffu) + 1u < touch_fifo_depth) {
			uint32_t word = 0;
			for (int j = 0; j < 4 && sent < length; j++, sent++) {
				word |= (uint32_t)(tx ? tx[sent] : 0u) << (8 * j);
			}
			touch_wr(touch_se, GENI_TX_FIFO, word);
		}
		status = touch_rd(touch_se, GENI_M_IRQ_STATUS);
		geni_drain(rx, length, &received);
		if (status & M_ERRORS) {
			break;
		}
		if (status & M_CMD_DONE) {
			geni_drain(rx, length, &received);
			touch_wr(touch_se, GENI_M_IRQ_CLEAR, status);
			if (received == length) {
				return true;
			}
			break;
		}
	}
	geni_recover();
	return false;
}

static bool
goodix_read(uint32_t addr, uint8_t *data, uint32_t len)
{
	static uint8_t tx[8 + GOODIX_MAX_READ];
	static uint8_t rx[8 + GOODIX_MAX_READ];
	if (len > GOODIX_MAX_READ) {
		return false;
	}
	tx[0] = 0xf1u;
	tx[1] = (uint8_t)(addr >> 24);
	tx[2] = (uint8_t)(addr >> 16);
	tx[3] = (uint8_t)(addr >> 8);
	tx[4] = (uint8_t)addr;
	tx[5] = 0xffu;
	tx[6] = 0xffu;
	tx[7] = 0xffu;
	memset(tx + 8, 0, len);
	if (!geni_transfer(tx, rx, 8u + len)) {
		return false;
	}
	memcpy(data, rx + 8, len);
	return true;
}

static bool
goodix_write(uint32_t addr, const uint8_t *data, uint32_t len)
{
	static uint8_t tx[8 + GOODIX_MAX_READ];
	if (len > GOODIX_MAX_READ) {
		return false;
	}
	tx[0] = 0xf0u;
	tx[1] = (uint8_t)(addr >> 24);
	tx[2] = (uint8_t)(addr >> 16);
	tx[3] = (uint8_t)(addr >> 8);
	tx[4] = (uint8_t)addr;
	memcpy(tx + 5, data, len);
	return geni_transfer(tx, NULL, 5u + len);
}

static bool
goodix_checksum_ok(const uint8_t *data, uint32_t len)
{
	if (len < 2) {
		return false;
	}
	uint32_t sum = 0;
	bool blank = true;
	for (uint32_t i = 0; i < len - 2; i++) {
		sum += data[i];
		blank &= (data[i] == 0 || data[i] == 0xffu);
	}
	return !blank && ((uint16_t)sum == (uint16_t)(data[len - 2] | ((uint16_t)data[len - 1] << 8)));
}

static uint16_t
goodix_le16(const uint8_t *p)
{
	return (uint16_t)(p[0] | ((uint16_t)p[1] << 8));
}

static uint32_t
goodix_le32(const uint8_t *p)
{
	return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static bool
goodix_probe(void)
{
	uint8_t version[28];
	static uint8_t info[GOODIX_MAX_READ];

	/* Reset chip */
	touch_gpio_set(PIN_RESET, false);
	delay(2000);
	touch_gpio_set(PIN_RESET, true);
	touch_wait(100);

	if (!goodix_read(GOODIX_FW_VERSION, version, sizeof(version))) {
		printf("MIAMI TOUCH: read FW_VERSION failed\n");
		return false;
	}
	if (!goodix_checksum_ok(version, sizeof(version))) {
		printf("MIAMI TOUCH: bad FW_VERSION checksum: %02x %02x %02x %02x...\n",
		    version[0], version[1], version[2], version[3]);
		/* Try probe fallback */
	} else {
		printf("MIAMI TOUCH: chip \"%.6s\", firmware \"%.8s\" %02x.%02x.%02x.%02x, sensor %u\n",
		    (const char *)version, (const char *)version + 10,
		    version[18], version[19], version[20], version[21], version[23]);
	}

	if (!goodix_read(GOODIX_IC_INFO, info, 2)) {
		printf("MIAMI TOUCH: read IC_INFO header failed\n");
		return false;
	}
	uint32_t length = goodix_le16(info);
	if (length >= 40 && length < GOODIX_MAX_READ && goodix_read(GOODIX_IC_INFO, info, length)) {
		uint32_t offset = 2u + 16u + 10u + 4u;
		for (int i = 0; i < 5 && offset < length; i++) {
			offset += 1u + 2u * info[offset];
		}
		if (offset + 48u + 2u <= length) {
			touch_report_addr = goodix_le32(info + offset + 44u);
			printf("MIAMI TOUCH: dynamic report addr=%#x\n", touch_report_addr);
		}
	}

	if (touch_report_addr == 0) {
		/* Fallback to standard Berlin-D report address */
		touch_report_addr = 0x10200u;
		printf("MIAMI TOUCH: using standard Berlin report addr=%#x\n", touch_report_addr);
	}
	return true;
}

static void
touch_thread(void *arg, wait_result_t result)
{
	static uint8_t report[8 + 8 * GOODIX_MAX_TOUCHES + 2];
	const uint8_t zero = 0;
	(void)arg;
	(void)result;

	printf("MIAMI TOUCH: polling thread started (report_addr=%#x)\n", touch_report_addr);

	for (;;) {
		bool int_active = !touch_gpio_get(PIN_INT);
		if (int_active || (touch_state[0].down || touch_state[1].down)) {
			if (goodix_read(touch_report_addr, report, 8 + 8 * 2 + 2) && report[0] != 0) {
				uint32_t count = report[2] & 0x0fu;
				if ((report[0] & GOODIX_STATUS_TOUCH) && count > 2 && count <= GOODIX_MAX_TOUCHES) {
					(void)goodix_read(touch_report_addr + 8u, report + 8u, 8u * count + 2u);
				}
				/* Acknowledge event */
				goodix_write(touch_report_addr, &zero, 1u);

				if (report[0] & GOODIX_STATUS_TOUCH) {
					bool seen[GOODIX_MAX_TOUCHES] = {false};
					for (uint32_t i = 0; i < count && i < GOODIX_MAX_TOUCHES; i++) {
						const uint8_t *t = report + 8u + 8u * i;
						uint32_t id = t[0] >> 4;
						if (id >= GOODIX_MAX_TOUCHES) continue;
						uint32_t rx = goodix_le16(t + 2);
						uint32_t ry = goodix_le16(t + 4);

						/* Map coordinates to 1080x2400 */
						int x = (int)(rx > 10800 ? 1079 : (rx * 1080 / 10800));
						int y = (int)(ry > 24000 ? 2399 : (ry * 2400 / 24000));

						seen[id] = true;
						touch_state[id].down = true;
						touch_state[id].x = x;
						touch_state[id].y = y;
						miami_hid_touch(id, 1, x, y);
					}
					for (uint32_t id = 0; id < GOODIX_MAX_TOUCHES; id++) {
						if (touch_state[id].down && !seen[id]) {
							touch_state[id].down = false;
							miami_hid_touch(id, 0, touch_state[id].x, touch_state[id].y);
						}
					}
				}
			}
		}
		touch_wait(10); /* 100 Hz poll */
	}
}

void
miami_touch_init(void)
{
	int enabled = 1;
	thread_t thread;

	if (touch_started) {
		return;
	}
	touch_started = true;

	(void)PE_parse_boot_argn("miamitouch", &enabled, sizeof(enabled));
	if (!enabled) {
		printf("MIAMI TOUCH: disabled (miamitouch=0)\n");
		return;
	}

	touch_se = ml_io_map(TOUCH_SE_PA, 0x4000);
	touch_gcc = ml_io_map(TOUCH_GCC_PA, 0x1f0000);
	touch_tlmm = ml_io_map(TOUCH_TLMM_PA, 0x800000);

	if (!touch_se || !touch_gcc || !touch_tlmm) {
		printf("MIAMI TOUCH: MMIO mapping failed (se=%p gcc=%p tlmm=%p)\n",
		    (void *)touch_se, (void *)touch_gcc, (void *)touch_tlmm);
		return;
	}

	touch_clocks_init();
	touch_pins_init();

	if (!geni_spi_init()) {
		printf("MIAMI TOUCH: GENI SPI initialization failed\n");
		return;
	}

	if (!goodix_probe()) {
		printf("MIAMI TOUCH: Goodix chip probe returned false; starting worker anyway\n");
	}

	kern_return_t kr = kernel_thread_start(touch_thread, NULL, &thread);
	if (kr == KERN_SUCCESS) {
		thread_deallocate(thread);
		printf("MIAMI TOUCH: hardware driver initialized\n");
	} else {
		printf("MIAMI TOUCH: kernel_thread_start failed %d\n", kr);
	}
}
#endif /* ARM64_BOARD_CONFIG_MIAMI */
