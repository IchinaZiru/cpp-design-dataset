class Memory {
public:
    unsigned char mem[MEMORY_SIZE];
    unsigned char placeholder;

    Memory() : placeholder(0) {
        std::memset(mem, 0, MEMORY_SIZE);
    }

    bool check_addr(unsigned int addr) {
        return addr >= 0 && addr < MEMORY_SIZE;
    }

    Immediate read_word(unsigned int addr) {
        if (!check_addr(addr)) {
            return 0;
        }
        return *reinterpret_cast<Immediate*>(&mem[addr]);
    }

    void write_word(unsigned int addr, Immediate imm) {
        if (check_addr(addr)) {
            *reinterpret_cast<Immediate*>(&mem[addr]) = imm;
        }
    }

    unsigned short read_ushort(unsigned int addr) {
        if (!check_addr(addr) || !check_addr(addr + 1)) {
            return 0;
        }
        return *reinterpret_cast<unsigned short*>(&mem[addr]);
    }

    void write_ushort(unsigned int addr, unsigned short imm) {
        if (check_addr(addr) && check_addr(addr + 1)) {
            *reinterpret_cast<unsigned short*>(&mem[addr]) = imm;
        }
    }

    unsigned char &operator[](unsigned int addr) {
        if (!check_addr(addr)) {
            return placeholder;
        }
        return mem[addr];
    }

    void debug() {
        for (unsigned int i = 0x1FF90; i < 0x20000; ++i) {
            std::cout << std::hex << static_cast<int>(mem[i]) << " ";
            if ((i + 1) % 16 == 0) {
                std::cout << std::endl;
            }
        }
    }
};