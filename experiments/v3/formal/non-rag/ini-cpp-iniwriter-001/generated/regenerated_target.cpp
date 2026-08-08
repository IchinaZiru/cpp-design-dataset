inline static void write(const std::string& filepath, const INIReader& reader, const bool overwrite = false) {
    if (!overwrite && std::ifstream(filepath)) {
        throw std::runtime_error("File already exists and overwrite is false.");
    }

    std::ofstream file(filepath);
    if (!file.is_open()) {
        throw std::runtime_error("Failed to open file for writing.");
    }

    auto sections = reader.Sections();
    for (const auto& section : sections) {
        file << "[" << section << "]\n";
        auto keys = reader.Keys(section);
        for (const auto& key : keys) {
            file << key << "=" << reader.Get(section, key) << "\n";
        }
        file << "\n"; // Add a newline between sections
    }
}