#include <stdint.h>

struct uart_chipflow_regs {
    uint32_t config;
    uint32_t phy_config;
    uint32_t status;
    uint32_t data;
};


struct uart_chipflow_regs *const UART_RX = (struct uart_chipflow_regs*)(0xb2000000);
struct uart_chipflow_regs *const UART_TX = (struct uart_chipflow_regs*)(0xb2000200);

static const uint32_t divisor  = (48000000 / 115200 - 1);

static void uart_init() {
    UART_RX->config = 0;
    UART_TX->config = 0;
    UART_RX->phy_config = divisor & 0x00FFFFFF;
    UART_TX->phy_config = divisor & 0x00FFFFFF;
    UART_RX->config = 1;
    UART_TX->config = 1;
};

static void putc(char c) {
    if (c == '\n')
        putc('\r');
    while (!(UART_TX->status & 0x1));
        ;
    UART_TX->data = (uint32_t)c;
}

static void puts(const char *s) {
    while (*s != 0)
        putc(*s++);
}


static void puthex(uint32_t x) {
    for (int i = 7; i >= 0; i--) {
        uint8_t nib = (x >> (4 * i)) & 0xF;
        if (nib <= 9)
            putc('0' + nib);
        else
            putc('A' + (nib - 10));
    }
}

extern uint32_t flashio_worker_begin;
extern uint32_t flashio_worker_end;

struct qspi_flash_regs {
    uint32_t config;
    uint32_t raw_control;
    uint32_t raw_tx_data;
    uint32_t raw_rx_data;
};

struct qspi_flash_regs *const QSPI_FLASH = (struct qspi_flash_regs*)(0xb0000000);

void flashio(uint8_t *data, int len, uint8_t wrencmd)
{
    volatile uint32_t func[&flashio_worker_end - &flashio_worker_begin];

    // Can't execute off flash while talking to it, so copy IO code to SRAM
    uint32_t *src_ptr = &flashio_worker_begin;
    volatile uint32_t *dst_ptr = func;

    while (src_ptr != &flashio_worker_end)
        *(dst_ptr++) = *(src_ptr++);

    __asm__ volatile ("fence.i" : : : "memory");

    ((void(*)(uint8_t*, uint32_t, uint32_t))func)(data, len, wrencmd);
}

void read_flash_id()
{
    uint8_t buffer[5] = { 0x9F, /* zeros */ };
    flashio(buffer, 5, 0);

    uint32_t id = 0;
    for (int i = 1; i <= 4; i++) {
        id = id << 8U;
        id |= buffer[i];
    }
    puts("Flash ID: ");
    puthex(id);
    puts("\n");
}

void set_flash_qspi_flag()
{
    uint8_t buffer[8];

    // Read Configuration Registers (RDCR1 35h)
    buffer[0] = 0x35;
    buffer[1] = 0x00; // rdata
    flashio(buffer, 2, 0);
    uint8_t sr2 = buffer[1];

    // Write Enable Volatile (50h) + Write Status Register 2 (31h)
    buffer[0] = 0x31;
    buffer[1] = sr2 | 2; // Enable QSPI
    flashio(buffer, 2, 0x50);
}

void enter_qspi_mode() {
    QSPI_FLASH->config = (0x1U << 3U) | (0x03U << 1U); // 1 dummy byte, X4 mode
}

void main() {
    uart_init();
    puts("Hello World!\n");
    read_flash_id();
    set_flash_qspi_flag();
    puts("Set QSPI flag\n");
    enter_qspi_mode();
    puts("In QSPI mode\n");
}
