class Parser {
public:
    static unsigned parse_hex(const std::string &hex) {
        char *end;
        return static_cast<unsigned>(std::strtol(hex.c_str(), &end, 16));
    }

    static void parse(std::istream &in, Memory &mem) {
        if (!in) {
            std::cerr << "Error: Invalid input stream." << std::endl;
            return;
        }

        unsigned base_addr = 0;
        std::string line;
        while (std::getline(in, line)) {
            if (!line.empty() && line[0] == '@') {
                base_addr = parse_hex(line.substr(1));
            } else {
                unsigned data = parse_hex(line);
                mem.write_word(base_addr, data);
                base_addr += 4;
            }
        }
    }

    static void parse_hex(std::istream &in, Memory &mem) {
        if (!in) {
            std::cerr << "Error: Invalid input stream." << std::endl;
            return;
        }

        unsigned base_addr = 0;
        std::string hex_data;
        while (std::getline(in, hex_data)) {
            unsigned data = parse_hex(hex_data);
            mem.write_word(base_addr, data);
            base_addr += 4;
        }
    }
};