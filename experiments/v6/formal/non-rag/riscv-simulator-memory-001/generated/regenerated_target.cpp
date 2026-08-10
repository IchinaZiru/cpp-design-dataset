class Memory {
public:
    unsigned char mem[MEMORY_SIZE];
    unsigned char placeholder;

    Memory() : placeholder(0) {
        memset(mem, 0, sizeof(mem));
    }

    bool check_addr(unsigned int addr) {
        return addr < MEMORY_SIZE;
    }

    Immediate read_word(unsigned int addr) {
        if (check_addr(addr)) {
            return *reinterpret_cast<Immediate*>(mem + addr);
        }
        return 0;
    }

    void write_word(unsigned int addr, Immediate imm) {
        if (check_addr(addr)) {
            *reinterpret_cast<Immediate*>(mem + addr) = imm;
        }
    }

    unsigned short read_ushort(unsigned int addr) {
        if (check_addr(addr) && check_addr(addr + 1)) {
            return *reinterpret_cast<unsigned short*>(mem + addr);
        }
        return 0;
    }

    void write_ushort(unsigned int addr, unsigned short imm) {
        if (check_addr(addr) && check_addr(addr + 1)) {
            *reinterpret_cast<unsigned short*>(mem + addr) = imm;
        }
    }

    unsigned char &operator[](unsigned int addr) {
        if (check_addr(addr)) {
            return mem[addr];
        }
        return placeholder;
    }

    void debug() {
        for (int i = 0x20000 - 0x10; i < 0x20000 + 0x10; ++i) {
            std::cout << "mem[" << i << "] = " << static_cast<int>(mem[i]) << std::endl;
        }
    }
};