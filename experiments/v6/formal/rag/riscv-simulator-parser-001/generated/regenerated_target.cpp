class Parser {
public:
    static unsigned parse_hex(const std::string &hex) {
        return static_cast<unsigned>(strtol(hex.c_str(), NULL, 16));
    }

    static void parse(std::istream &in, Memory &mem) {
        if (!in) {
            std::cerr << "parse failed, invalid stream" << std::endl;
            return;
        }
        
        unsigned base_addr = 0;
        std::string line;
        
        while (std::getline(in, line)) {
            if (line.empty()) continue;
            
            if (line[0] == '@') {
                base_addr = static_cast<unsigned>(strtol(line.c_str() + 1, NULL, 16));
            } else {
                std::stringstream ss(line);
                std::string hex;
                
                while (ss >> hex) {
                    if (hex.length() == 0) continue;
                    
                    char data = static_cast<char>(parse_hex(hex));
                    mem[base_addr++] = data;
                }
            }
        }
    }

    static void parse_hex(std::istream &in, Memory &mem) {
        if (!in) {
            std::cerr << "parse failed, invalid stream" << std::endl;
            return;
        }
        
        unsigned base_addr = 0;
        std::string hex;
        
        while (in >> hex) {
            if (hex.length() == 0) continue;
            
            mem.write_word(base_addr, parse_hex(hex));
            base_addr += 4;
        }
    }
};