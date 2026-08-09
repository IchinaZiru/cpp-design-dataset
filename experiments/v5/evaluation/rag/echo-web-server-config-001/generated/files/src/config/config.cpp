#include "config.h"
#include <yaml-cpp/yaml.h>

namespace ws {

namespace cfg {

void ExtractMembers(const YAML::Node& root, std::map<std::string, YAML::Node>& members) {
    if (root.IsMap()) {
        for (const auto& [key, value] : root) {
            members[key.as<std::string>()] = value;
        }
    }
}

}  // namespace cfg

}  // namespace ws
