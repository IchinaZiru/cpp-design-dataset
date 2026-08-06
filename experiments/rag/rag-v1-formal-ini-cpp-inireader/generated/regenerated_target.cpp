#include <cstddef>
#include <cstdio>
#include <fstream>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <type_traits>
#include <unordered_map>
#include <utility>
#include <vector>

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
        std::ifstream file(filename);
        if (!file.is_open()) {
            _error = -1;
            throw std::runtime_error("ini file not found.");
        }
        try {
            Parse(std::string((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>()));
        } catch (const std::bad_alloc&) {
            _error = -2;
            throw std::runtime_error("memory alloc error");
        }
    }

    /**
     * @brief Construct an INIReader object from a file pointer
     * @param file A pointer to the INI file to parse
     * @throws std::runtime_error if there is an error parsing the INI file
     */
    INIReader(std::FILE* file) {
        if (!file) {
            _error = -1;
            throw std::runtime_error("ini file not found.");
        }
        try {
            std::string content;
            char buffer[4096];
            while (std::fgets(buffer, sizeof(buffer), file)) {
                content.append(buffer);
            }
            Parse(content);
        } catch (const std::bad_alloc&) {
            _error = -2;
            throw std::runtime_error("memory alloc error");
        }
    }

    /**
     * @brief Return the result of the parse, i.e., 0 on success
     * @throws std::runtime_error on file open or parse error
     */
    int ParseError() const {
        if (_error == -1) throw std::runtime_error("ini file not found.");
        if (_error == -2) throw std::runtime_error("memory alloc error");
        if (_error > 0) throw std::runtime_error("parse error on line no: " + std::to_string(_error));
        return _error;
    }

    /**
     * @brief Return the list of sections found in ini file
     * @return The list of sections found in ini file
     */
    std::set<std::string> Sections() const {
        std::set<std::string> sections;
        for (const auto& pair : _values) {
            sections.insert(pair.first);
        }
        return sections;
    }

    /**
     * @brief Return the list of keys in the given section
     * @param section The section name
     * @return The list of keys in the given section
     */
    std::set<std::string> Keys(const std::string& section) const {
        const auto& sec = GetSection(section);
        std::set<std::string> keys;
        for (const auto& pair : sec) {
            keys.insert(pair.first);
        }
        return keys;
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
        return Converter<T>(FindEntry(section, name));
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
            return Converter<T>(FindEntry(section, name));
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
        std::istringstream iss(FindEntry(section, name));
        std::vector<T> result;
        std::string token;
        while (iss >> token) {
            try {
                result.push_back(Converter<T>(token));
            } catch (const std::runtime_error&) {
                throw std::runtime_error("parse error on value '" + token + "'");
            }
        }
        return result;
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
        sec[name] = V2String(v);
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
        sec[name] = Vec2String(vs);
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
        FindEntry(section, name) = V2String(v);
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
        FindEntry(section, name) = Vec2String(vs);
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
        } else {
            std::istringstream iss(s);
            T value;
            if (!(iss >> value)) {
                throw std::runtime_error("parse error on value '" + s + "'");
            }
            return value;
        }
    }

    /// Parse a boolean token: 1/0/true/false/yes/no/on/off, case-insensitive;
    /// throws std::runtime_error on anything else.
    bool BoolConverter(std::string s) const {
        std::transform(s.begin(), s.end(), s.begin(), ::tolower);
        if (s == "1" || s == "true" || s == "yes" || s == "on") return true;
        if (s == "0" || s == "false" || s == "no" || s == "off") return false;
        throw std::runtime_error("parse error on boolean value '" + s + "'");
    }

    /// Serialize a value with operator<<.
    template <typename T>
    std::string V2String(const T& v) const {
        std::ostringstream oss;
        if (!(oss << v)) {
            throw std::runtime_error("serialization error on value");
        }
        return oss.str();
    }

    /// Serialize a vector as space-separated values.
    template <typename T>
    std::string Vec2String(const std::vector<T>& v) const {
        std::ostringstream oss;
        for (size_t i = 0; i < v.size(); ++i) {
            if (i > 0) oss << " ";
            oss << V2String(v[i]);
        }
        return oss.str();
    }

   private:
    const std::unordered_map<std::string, std::string>& GetSection(
        const std::string& section) const {
        auto it = _values.find(section);
        if (it == _values.end()) {
            throw std::runtime_error("section '" + section + "' not found.");
        }
        return it->second;
    }

    std::string& FindEntry(const std::string& section,
                           const std::string& name) {
        auto& sec = _values[section];
        auto it = sec.find(name);
        if (it == sec.end()) {
            throw std::runtime_error("key '" + name + "' not exist in section '" + section + "'.");
        }
        return it->second;
    }

    /* Parse the whole ini content. Grammar:
       - `[section]` lines open a section; text after ']' is ignored
       - `name = value` or `name : value` pairs, whitespace-trimmed
       - lines starting with ';' or '#' are comments
       - a ';' preceded by whitespace starts an inline comment
       Records the first faulty line in _error and stops there. Throws on
       duplicate keys. */
    void Parse(std::string_view content) {
        std::istringstream iss(std::string(content));
        std::string line;
        size_t line_number = 0;
        std::string current_section;
        while (std::getline(iss, line)) {
            ++line_number;
            // Trim leading and trailing whitespace
            size_t start = line.find_first_not_of(" \t");
            if (start == std::string::npos) continue; // Skip empty lines
            size_t end = line.find_last_not_of(" \t");
            line = line.substr(start, end - start + 1);

            // Check for comments
            if (line[0] == ';' || line[0] == '#') continue;

            // Check for section headers
            if (line[0] == '[') {
                size_t close_bracket = line.find(']');
                if (close_bracket == std::string::npos) {
                    _error = line_number;
                    return;
                }
                current_section = line.substr(1, close_bracket - 1);
                continue;
            }

            // Check for key-value pairs
            size_t equals_pos = line.find('=');
            if (equals_pos == std::string::npos) {
                equals_pos = line.find(':');
                if (equals_pos == std::string::npos) {
                    _error = line_number;
                    return;
                }
            }

            std::string key = line.substr(0, equals_pos);
            std::string value = line.substr(equals_pos + 1);

            // Trim whitespace around key and value
            start = key.find_first_not_of(" \t");
            end = key.find_last_not_of(" \t");
            if (start != std::string::npos && end != std::string::npos) {
                key = key.substr(start, end - start + 1);
            }

            start = value.find_first_not_of(" \t");
            end = value.find_last_not_of(" \t");
            if (start != std::string::npos && end != std::string::npos) {
                value = value.substr(start, end - start + 1);
            }

            // Check for inline comments
            size_t comment_pos = value.find(';');
            if (comment_pos != std::string::npos) {
                value = value.substr(0, comment_pos);
                end = value.find_last_not_of(" \t");
                if (end != std::string::npos) {
                    value = value.substr(0, end + 1);
                }
            }

            // Insert key-value pair into the current section
            auto& sec = _values[current_section];
            if (sec.find(key) != sec.end()) {
                _error = line_number;
                return;
            }
            sec[key] = value;
        }
    }
};