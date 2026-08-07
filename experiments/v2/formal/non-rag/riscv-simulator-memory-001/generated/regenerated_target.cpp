class Memory {
public:
    unsigned char mem[MEMORY_SIZE];
    unsigned char placeholder;

    Memory() : placeholder(0) {
        std::memset(mem, 0, MEMORY_SIZE);
    }

    bool check_addr(unsigned int addr) {
        return addr < MEMORY_SIZE;
    }

    Immediate read_word(unsigned int addr) {
        if (!check_addr(addr)) {
            return 0;
        }
        Immediate value = 0;
        for (int i = 0; i < 4; ++i) {
            value |= static_cast<Immediate>(mem[addr + i]) << (i * 8);
        }
        return value;
    }

    void write_word(unsigned int addr, Immediate imm) {
        if (!check_addr(addr)) {
            return;
        }
        for (int i = 0; i < 4; ++i) {
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
        for (int i = 0; i < 16; ++i) { // Output first 16 bytes for debugging
            std::cout << static_cast<int>(mem[i]) << " ";
        }
        std::cout << std::endl;
    }
};