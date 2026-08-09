inline static void write(const std::string& filepath,
                         const INIReader& reader,
                         const bool overwrite = false) {
    if (!overwrite) {
        std::ifstream file(filepath);
        if (file.is_open()) {
            throw std::runtime_error("File already exists and overwrite is false.");
        }
    }

    std::ofstream out(filepath);
    if (!out.is_open()) {
        throw std::runtime_error("Failed to open file for writing.");
    }

    for (const auto& section : reader.Sections()) {
        out << "[" << section << "]\n";
        for (const auto& key : reader.Keys(section)) {
            out << key << "=" << reader.Get(section, key) << "\n";
        }
    }
}