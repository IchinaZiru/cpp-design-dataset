class Memory {
public:
    unsigned char mem[MEMORY_SIZE];
    unsigned char placeholder;

    Memory() : placeholder(0) {
        std::memset(mem, 0, sizeof(mem));
    }

    bool check_addr(unsigned int addr) {
        return addr < MEMORY_SIZE;
    }

    Immediate read_word(unsigned int addr) {
        if (check_addr(addr)) {
            return *reinterpret_cast<Immediate*>(&mem[addr]);
        }
        return 0;
    }

    void write_word(unsigned int addr, Immediate imm) {
        if (check_addr(addr)) {
            *reinterpret_cast<Immediate*>(&mem[addr]) = imm;
        }
    }

    unsigned short read_ushort(unsigned int addr) {
        if (check_addr(addr + 1)) { // Ensure we can read 2 bytes
            return *reinterpret_cast<unsigned short*>(&mem[addr]);
        }
        return 0;
    }

    void write_ushort(unsigned int addr, unsigned short imm) {
        if (check_addr(addr + 1)) { // Ensure we can write 2 bytes
            *reinterpret_cast<unsigned short*>(&mem[addr]) = imm;
        }
    }

    unsigned char &operator[](unsigned int addr) {
        if (check_addr(addr)) {
            return mem[addr];
        }
        return placeholder;
    }

    void debug() {
        for (size_t i = 0; i < MEMORY_SIZE; ++i) {
            std::cout << std::hex << static_cast<int>(mem[i]) << " ";
            if ((i + 1) % 16 == 0) {
                std::cout << std::endl;
            }
        }
    }
};