class Memory {
public:
    unsigned char mem[MEMORY_SIZE];
    unsigned char placeholder;

    Memory() {
        std::memset(mem, 0, sizeof(mem));
        placeholder = 0;
    }

    bool check_addr(unsigned int addr) {
        return addr < MEMORY_SIZE;
    }

    Immediate read_word(unsigned int addr) {
        if (check_addr(addr)) {
            return *(Immediate *)(mem + addr);
        }
        return 0;
    }

    void write_word(unsigned int addr, Immediate imm) {
        if (check_addr(addr)) {
            *(Immediate *)(mem + addr) = imm;
        }
    }

    unsigned short read_ushort(unsigned int addr) {
        if (check_addr(addr) && check_addr(addr + 1)) {
            return *(unsigned short *)(mem + addr);
        }
        return 0;
    }

    void write_ushort(unsigned int addr, unsigned short imm) {
        if (check_addr(addr) && check_addr(addr + 1)) {
            *(unsigned short *)(mem + addr) = imm;
        }
    }

    unsigned char &operator[](unsigned int addr) {
        if (check_addr(addr)) {
            return mem[addr];
        }
        return placeholder;
    }

    void debug() {
        for (unsigned int i = 0; i < MEMORY_SIZE; ++i) {
            std::cout << std::hex << static_cast<int>(mem[i]) << " ";
            if ((i + 1) % 16 == 0) {
                std::cout << std::endl;
            }
        }
    }
};