class Memory {
public:
    unsigned char mem[MEMORY_SIZE];
    unsigned char placeholder;

    Memory() : placeholder(0) {
        std::memset(mem, 0, MEMORY_SIZE);
    }

    bool check_addr(unsigned int addr) {
        return addr <= MEMORY_SIZE - sizeof(Immediate);
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
        if (addr <= MEMORY_SIZE - sizeof(unsigned short)) {
            return *reinterpret_cast<unsigned short*>(mem + addr);
        }
        return 0;
    }

    void write_ushort(unsigned int addr, unsigned short imm) {
        if (addr <= MEMORY_SIZE - sizeof(unsigned short)) {
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
        for (unsigned int i = 0x20010; i < 0x20020; ++i) {
            std::cout << std::hex << static_cast<int>(mem[i]) << " ";
        }
        std::cout << std::endl;
    }
};