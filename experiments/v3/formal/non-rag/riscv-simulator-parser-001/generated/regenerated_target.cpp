class Parser {
public:
    static unsigned parse_hex(const std::string &hex) {
        unsigned value;
        std::stringstream ss(hex);
        ss >> std::hex >> value;
        return value;
    }

    static void parse(std::istream &in, Memory &mem) {
        if (!in) {
            std::cerr << "Invalid input stream" << std::endl;
            return;
        }

        std::string line;
        unsigned base_addr = 0;

        while (std::getline(in, line)) {
            if (line.empty()) continue;

            if (line[0] == '@') {
                base_addr = parse_hex(line.substr(1));
            } else {
                std::stringstream ss(line);
                std::string hex_value;
                unsigned addr = base_addr;

                while (ss >> hex_value) {
                    mem.write_byte(addr++, parse_hex(hex_value));
                }
            }
        }
    }

    static void parse_hex(std::istream &in, Memory &mem) {
        if (!in) {
            std::cerr << "Invalid input stream" << std::endl;
            return;
        }

        unsigned addr = 0;
        std::string hex_word;

        while (in >> hex_word) {
            mem.write_word(addr, parse_hex(hex_word));
            addr += 4; // Increment address by 4 bytes for each word
        }
    }
};