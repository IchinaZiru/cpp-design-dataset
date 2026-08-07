inline static void write(const std::string& filepath, const INIReader& reader, const bool overwrite = false) {
    if (!overwrite && std::ifstream(filepath)) {
        throw std::runtime_error("file: " + filepath + " already exists.");
    }

    std::ofstream ofs(filepath);
    if (!ofs.is_open()) {
        throw std::runtime_error("cannot open output file: " + filepath);
    }

    for (const auto& section : reader.Sections()) {
        ofs << "[" << section << "]\n";
        for (const auto& key : reader.Keys(section)) {
            ofs << key << "=" << reader.Get(section, key) << "\n";
        }
    }
}