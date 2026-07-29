if (!overwrite) {
    std::ifstream file(filepath);
    if (file.is_open()) {
        throw std::runtime_error("File already exists.");
    }
}

std::ofstream outFile(filepath);
if (!outFile.is_open()) {
    throw std::runtime_error("Cannot open output file.");
}

for (const auto& section : reader.Sections()) {
    outFile << "[" << section << "]" << std::endl;
    for (const auto& key : reader.Keys(section)) {
        outFile << key << "=" << reader.Get(section, key) << std::endl;
    }
}
