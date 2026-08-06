class Memory {
public:
    unsigned char mem[MEMORY_SIZE];
    unsigned char placeholder;

    Memory() : placeholder(0) {
        for (size_t i = 0; i < MEMORY_SIZE; ++i) {
            mem[i] = 0;
        }
    }

    bool check_addr(unsigned int addr) {
        return addr < MEMORY_SIZE;
    }

    Immediate read_word(unsigned int addr) {
        if (!check_addr(addr)) {
            return 0;
        }
        Immediate value = 0;
        for (size_t i = 0; i < sizeof(Immediate); ++i) {
            value |= static_cast<Immediate>(mem[addr + i]) << (i * 8);
        }
        return value;
    }

    void write_word(unsigned int addr, Immediate imm) {
        if (!check_addr(addr)) {
            return;
        }
        for (size_t i = 0; i < sizeof(Immediate); ++i) {
            mem[addr + i] = static_cast<unsigned char>((imm >> (i * 8)) & 0xFF);
        }
    }

    unsigned short read_ushort(unsigned int addr) {
        if (!check_addr(addr) || !check_addr(addr + 1)) {
            return 0;
        }
        return static_cast<unsigned short>(mem[addr]) | (static_cast<unsigned short>(mem[addr + 1]) << 8);
    }

    void write_ushort(unsigned int addr, unsigned short imm) {
        if (!check_addr(addr) || !check_addr(addr + 1)) {
            return;
        }
        mem[addr] = static_cast<unsigned char>(imm & 0xFF);
        mem[addr + 1] = static_cast<unsigned char>((imm >> 8) & 0xFF);
    }

    unsigned char &operator[](unsigned int addr) {
        if (!check_addr(addr)) {
            return placeholder;
        }
        return mem[addr];
    }

    void debug() {
        for (size_t i = 0; i < MEMORY_SIZE; ++i) {
            printf("%02X ", mem[i]);
            if ((i + 1) % 16 == 0) {
                printf("\n");
            }
        }
    }
};