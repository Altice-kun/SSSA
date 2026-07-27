#include <iostream>
#include <vector>
#include <string>
#include <algorithm>
#include <random>
#include <cmath>
#include <sstream>

struct Document {
    std::string id;
    std::string name;
    std::string content;
    std::string description;
    double context_score;
};

struct ActiveItem {
    Document doc;
    double score;
    double base;
    double p_field;
    bool locked;
};

std::string to_lower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(), ::tolower);
    return s;
}

std::tuple<double, double, double> calculate_sssa_score(const std::string& query_str, const Document& doc) {
    std::stringstream ss(query_str);
    std::string word;
    std::vector<std::string> query_words;
    while (ss >> word) {
        query_words.push_back(to_lower(word));
    }

    if (query_words.empty()) return {0.0, 0.0, 0.0};

    std::string name_txt = to_lower(doc.name);
    std::string content_txt = to_lower(doc.content);
    std::string desc_txt = to_lower(doc.description);
    std::string all_text = name_txt + " " + content_txt + " " + desc_txt;

    int matched_words = 0;
    for (const auto& w : query_words) {
        if (all_text.find(w) != std::string::npos) matched_words++;
    }
    double match_count_score = static_cast<double>(matched_words) / query_words.size();

    int total_tf = 0;
    for (const auto& w : query_words) {
        size_t pos = all_text.find(w);
        while (pos != std::string::npos) {
            total_tf++;
            pos = all_text.find(w, pos + w.length());
        }
    }

    double term_freq_score = std::min(1.0, std::log(1.0 + total_tf) / 3.0);
    double base_score = (match_count_score + term_freq_score + doc.context_score) / 3.0;

    std::vector<std::string> fields = {name_txt, content_txt, desc_txt};
    int hit_fields = 0;
    for (const auto& f : fields) {
        for (const auto& w : query_words) {
            if (f.find(w) != std::string::npos) {
                hit_fields++;
                break;
            }
        }
    }

    double p_field = (static_cast<double>(hit_fields) / fields.size()) * 100.0;
    double sssa_score = base_score * (p_field / 100.0);

    return {
        std::round(sssa_score * 10000.0) / 10000.0,
        std::round(base_score * 10000.0) / 10000.0,
        std::round(p_field * 10.0) / 10.0
    };
}

std::vector<ActiveItem> partition_into_10_buckets(std::vector<ActiveItem>& active_items) {
    std::vector<std::vector<ActiveItem>> buckets(10);
    for (const auto& item : active_items) {
        double comp_score = item.score * 0.7 + item.base * 0.3;
        int b_idx = static_cast<int>((1.0 - std::min(1.0, std::max(0.0, comp_score))) * 10);
        if (b_idx >= 10) b_idx = 9;
        buckets[b_idx].push_back(item);
    }

    std::random_device rd;
    std::mt19937 g(rd());
    std::vector<ActiveItem> partitioned;
    for (auto& b : buckets) {
        std::shuffle(b.begin(), b.end(), g);
        partitioned.insert(partitioned.end(), b.begin(), b.end());
    }
    return partitioned;
}
