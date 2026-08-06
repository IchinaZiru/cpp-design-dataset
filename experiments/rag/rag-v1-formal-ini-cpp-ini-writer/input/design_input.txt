/**
 * @brief Write the contents of an INIReader to an ini file.
 */
class INIWriter {
   public:
    INIWriter() = default;
    /**
     * @brief Write the contents of an INI file to a new file
     * @param filepath The path of the output file
     * @param reader The INIReader object to write to the file
     * @param overwrite Whether to just overwrite an existing file
     * @throws std::runtime_error if the output file already exists or cannot
     * be opened
     */
    inline static void write(const std::string& filepath,
                             const INIReader& reader,
                             const bool overwrite = false) {
        if (!overwrite && std::ifstream{filepath}) {
            throw std::runtime_error("file: " + filepath + " already exists.");
        }
        std::ofstream out{filepath};
        if (!out.is_open()) {
            throw std::runtime_error("cannot open output file: " + filepath);
        }
        for (const auto& section : reader.Sections()) {
            out << "[" << section << "]\n";
            for (const auto& key : reader.Keys(section)) {
                out << key << "=" << reader.Get(section, key) << "\n";
            }
        }
    }
};
