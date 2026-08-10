class INIReader {
   public:
    // Empty Constructor
    INIReader() = default;

    /**
     * @brief Construct an INIReader object from a file name
     * @param filename The name of the INI file to parse
     * @throws std::runtime_error if there is an error parsing the INI file
     */
    INIReader(const std::string& filename) {
        std::ifstream in{filename, std::ios::in | std::ios::binary};
        if (!in.is_open()) {
            throw std::runtime_error("ini file not found.");
        }
        in.seekg(0, std::ios::end);
        const auto size = in.tellg();
        if (size == -1) {
            throw std::runtime_error("memory alloc error");
        }
        std::string content;
        content.resize(static_cast<std::size_t>(size));
        in.seekg(0, std::ios::beg);
        in.read(&content[0], size);
        Parse(content);
    }

    /**
     * @brief Construct an INIReader object from a file pointer
     * @param file A pointer to the INI file to parse
     * @throws std::runtime_error if there is an error parsing the INI file
     */
    INIReader(std::FILE* file) {
        if (!file) {
            throw std::runtime_error("ini file not found.");
        }
        std::string content;
        char buf[1 << 15];
        std::size_t n = 0;
        while ((n = std::fread(buf, 1, sizeof(buf), file)) > 0) {
            content.append(buf, n);
        }
        if (std::feof(file) == 0 && std::ferror(file) != 0) {
            throw std::runtime_error("memory alloc error");
        }
        Parse(content);
    }

    /**
     * @brief Return the result of the parse, i.e., 0 on success
     * @throws std::runtime_error on file open or parse error
     */
    int ParseError() const {
        if (_error == -1) {
            throw std::runtime_error("ini file not found.");
        } else if (_error == -2) {
            throw std::runtime_error("memory alloc error");
        } else if (_error > 0) {
            throw std::runtime_error("parse error on line no: " + std::to_string(_error));
        }
        return _error;
    }

    /**
     * @brief Return the list of sections found in ini file
     * @return The list of sections found in ini file
     */
    std::set<std::string> Sections() const {
        std::set<std::string> retval;
        for (const auto& element : _values) {
            retval.insert(element.first);
        }
        return retval;
    }

    /**
     * @brief Return the list of keys in the given section
     * @param section The section name
     * @return The list of keys in the given section
     */
    std::set<std::string> Keys(const std::string& section) const {
        std::set<std::string> retval;
        const auto& sec = GetSection(section);
        for (const auto& element : sec) {
            retval.insert(element.first);
        }
        return retval;
    }

    /**
     * @brief Get the map representing the values in a section of the INI file
     * @param section The name of the section to retrieve
     * @return The map representing the values in the given section
     * @throws std::runtime_error if the section is not found
     */
    std::unordered_map<std::string, std::string> Get(
        const std::string& section) const {
        return GetSection(section);
    }

    /**
     * @brief Return the value of the given key in the given section
     * @param section The section name
     * @param name The key name
     * @return The value of the given key in the given section
     * @throws std::runtime_error if the section/key is not found or the
     * value cannot be parsed to type T
     */
    template <typename T = std::string>
    T Get(const std::string& section, const std::string& name) const {
        const auto& sec = GetSection(section);
        const auto value = sec.find(name);
        if (value == sec.end()) {
            throw std::runtime_error("key '" + name + "' not found in section '" + section + "'.");
        }
        return Converter<T>(value->second);
    }

    /**
     * @brief Return the value of the given key in the given section, return
     * default if not found
     * @param section The section name
     * @param name The key name
     * @param default_v The default value
     * @return The value of the given key in the given section, return default
     * if not found
     */
    template <typename T>
    T Get(const std::string& section, const std::string& name,
          T&& default_v) const {
        try {
            return Get<T>(section, name);
        } catch (const std::runtime_error&) {
            return std::forward<T>(default_v);
        }
    }

    /**
     * @brief Return the value array of the given key in the given section.
     * @param section The section name
     * @param name The key name
     * @return The value array of the given key in the given section.
     *
     * For example:
     * ```ini
     * [section]
     * key = 1 2 3 4
     * ```
     * ```cpp
     * const auto vs = ini.GetVector<int>("section", "key");
     * // vs = {1, 2, 3, 4}
     * ```
     */
    template <typename T = std::string>
    std::vector<T> GetVector(const std::string& section,
                             const std::string& name) const {
        const std::string value = Get(section, name);
        std::vector<T> vs;
        std::size_t i = 0;
        while (i < value.size()) {
            while (i < value.size() && detail::is_space(value[i])) ++i;
            if (i == value.size()) break;
            std::size_t j = i + 1;
            while (j < value.size() && !detail::is_space(value[j])) ++j;
            T v{};
            try {
                v = Converter<T>(value.substr(i, j - i));
            } catch (...) {
                throw std::runtime_error("cannot parse value " + value + " to vector<T>.");
            }
            vs.emplace_back(v);
            i = j;
        }
        return vs;
    }

    /**
     * @brief Return the value array of the given key in the given section,
     * return default if not found
     * @param section The section name
     * @param name The key name
     * @param default_v The default value
     * @return The value array of the given key in the given section, return
     * default if not found
     *
     * @see INIReader::GetVector
     */
    template <typename T>
    std::vector<T> GetVector(const std::string& section,
                             const std::string& name,
                             const std::vector<T>& default_v) const {
        try {
            return GetVector<T>(section, name);
        } catch (const std::runtime_error&) {
            return default_v;
        }
    }

    /**
     * @brief Insert a key-value pair into the INI file
     * @param section The section name
     * @param name The key name
     * @param v The value to insert
     * @throws std::runtime_error if the key already exists in the section
     */
    template <typename T = std::string>
    void InsertEntry(const std::string& section, const std::string& name,
                     const T& v) {
        auto& sec = _values[section];
        if (sec.find(name) != sec.end()) {
            throw std::runtime_error("duplicate key '" + name + "' in section '" + section + "'.");
        }
        sec.emplace(name, V2String(v));
    }

    /**
     * @brief Insert a vector of values into the INI file
     * @param section The section name
     * @param name The key name
     * @param vs The vector of values to insert
     * @throws std::runtime_error if the key already exists in the section
     */
    template <typename T = std::string>
    void InsertEntry(const std::string& section, const std::string& name,
                     const std::vector<T>& vs) {
        auto& sec = _values[section];
        if (sec.find(name) != sec.end()) {
            throw std::runtime_error("duplicate key '" + name + "' in section '" + section + "'.");
        }
        sec.emplace(name, Vec2String(vs));
    }

    /**
     * @brief Update a key-value pair in the INI file
     * @param section The section name
     * @param name The key name
     * @param v The new value to set
     * @throws std::runtime_error if the key does not exist in the section
     */
    template <typename T = std::string>
    void UpdateEntry(const std::string& section, const std::string& name,
                     const T& v) {
        auto& entry = FindEntry(section, name);
        entry = V2String(v);
    }

    /**
     * @brief Update a vector of values in the INI file
     * @param section The section name
     * @param name The key name
     * @param vs The new vector of values to set
     * @throws std::runtime_error if the key does not exist in the section
     */
    template <typename T = std::string>
    void UpdateEntry(const std::string& section, const std::string& name,
                     const std::vector<T>& vs) {
        auto& entry = FindEntry(section, name);
        entry = Vec2String(vs);
    }

   protected:
    /// Parse result: 0 on success, -1 on file open error, otherwise the
    /// number of the first faulty line.
    int _error = 0;
    /// Parsed content, as _values[section][name] = value.
    std::unordered_map<std::string,
                       std::unordered_map<std::string, std::string>>
        _values;

    /// Parse `s` as a `T`; throws std::runtime_error on failure.
    template <typename T>
    T Converter(const std::string& s) const {
        if constexpr (std::is_same_v<T, bool>) {
            return BoolConverter(s);
        } else if constexpr (std::is_integral_v<T> || std::is_floating_point_v<T>) {
            T v;
            auto [ptr, ec] = std::from_chars(s.data(), s.data() + s.size(), v);
            if (ec != std::errc()) {
                throw std::runtime_error("cannot parse value '" + s + "' to type<T>.");
            }
            return v;
        } else {
            return static_cast<T>(s);
        }
    }

    /// Parse a boolean token: 1/0/true/false/yes/no/on/off, case-insensitive;
    /// throws std::runtime_error on anything else.
    bool BoolConverter(std::string s) const {
        for (auto& c : s) c = tolower(c);
        static const std::unordered_map<std::string, bool> s2b{ {"1", true}, {"true", true}, {"yes", true}, {"on", true}, {"0", false}, {"false", false}, {"no", false}, {"off", false}, };
        const auto value = s2b.find(s);
        if (value == s2b.end()) {
            throw std::runtime_error("'" + s + "' is not a valid boolean value.");
        }
        return value->second;
    }

    /// Serialize a value with operator<<.
    template <typename T>
    std::string V2String(const T& v) const {
        std::ostringstream ss;
        ss << v;
        return ss.str();
    }

    /// Serialize a vector as space-separated values.
    template <typename T>
    std::string Vec2String(const std::vector<T>& v) const {
        std::ostringstream oss;
        for (std::size_t i = 0; i < v.size(); ++i) {
            if (i > 0) oss << " ";
            oss << V2String(v[i]);
        }
        return oss.str();
    }

   private:
    const std::unordered_map<std::string, std::string>& GetSection(
        const std::string& section) const {
        const auto sec = _values.find(section);
        if (sec == _values.end()) {
            throw std::runtime_error("section '" + section + "' not found.");
        }
        return sec->second;
    }

    std::string& FindEntry(const std::string& section,
                           const std::string& name) {
        auto sec = _values.find(section);
        if (sec == _values.end()) {
            throw std::runtime_error("section '" + section + "' not found.");
        }
        auto value = sec->second.find(name);
        if (value == sec->second.end()) {
            throw std::runtime_error("key '" + name + "' not exist in section '" + section + "'.");
        }
        return value->second;
    }

    /* Parse the whole ini content. Grammar:
       - `[section]` lines open a section; text after ']' is ignored
       - `name = value` or `name : value` pairs, whitespace-trimmed
       - lines starting with ';' or '#' are comments
       - a ';' preceded by whitespace starts an inline comment
       Records the first faulty line in _error and stops there. Throws on
       duplicate keys. */
    void Parse(std::string_view content) {
        constexpr std::string_view bom{"\xEF\xBB\xBF", 3};
        if (content.starts_with(bom)) {
            content.remove_prefix(bom.size());
        }
        std::string section;
        std::unordered_map<std::string, std::string>* values = nullptr;
        int lineno = 0;
        while (!content.empty()) {
            ++lineno;
            const auto eol = content.find('\n');
            const auto line = detail::trim(content.substr(0, eol));
            if (line.empty() || line.front() == ';' || line.front() == '#') {
                content.remove_prefix(eol == std::string_view::npos ? content.size() : eol + 1);
                continue;
            }
            const auto end = detail::find_char_or_comment(line.substr(1), "]");
            if (line.front() == '[' && end != std::string_view::npos) {
                section.assign(line.data() + 1, end);
                values = &_values[section];
                content.remove_prefix(eol == std::string_view::npos ? content.size() : eol + 1);
                continue;
            }
            if (!values) {
                _error = lineno;
                return;
            }
            const auto sep = detail::find_char_or_comment(line, "=:");
            if (sep == std::string_view::npos) {
                _error = lineno;
                return;
            }
            const auto name = detail::rtrim(line.substr(0, sep));
            auto value = line.substr(sep + 1);
            const auto comment = detail::find_char_or_comment(value, {});
            if (comment != std::string_view::npos) {
                value.remove_prefix(comment);
            }
            value = detail::trim(value);
            if (values->emplace(std::string(name), std::string(value)).second == false) {
                _error = lineno;
                return;
            }
            content.remove_prefix(eol == std::string_view::npos ? content.size() : eol + 1);
        }
    }
};