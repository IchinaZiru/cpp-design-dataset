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
        /* REGENERATED_BODY */
    }
};
