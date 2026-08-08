inline static void write(const std::string& filepath,
                         const INIReader& reader,
                         const bool overwrite = false) {
    if (!overwrite) {
        std::ifstream file(filepath);
        if (file.is_open()) {
            throw std::runtime_error("File already exists and overwrite is false.");
        }
    }

    std::ofstream outFile(filepath);
    if (!outFile.is_open()) {
        throw std::runtime_error("Failed to open file for writing.");
    }

    auto sections = reader.Sections();
    for (const auto& section : sections) {
        outFile << "[" << section << "]\n";
        auto keys = reader.Keys(section);
        for (const auto& key : keys) {
            outFile << key << "=" << reader.Get(section, key) << "\n";
        }
    }
}