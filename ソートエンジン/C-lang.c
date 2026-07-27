#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

typedef struct {
    char id[32];
    char name[128];
    char content[256];
    char description[128];
    double context_score;
} Document;

typedef struct {
    Document doc;
    double score;
    double base;
    double p_field;
    int locked;
} ActiveItem;

// 小文字変換ヘルパー
void to_lower_str(char *dest, const char *src) {
    int i = 0;
    while (src[i]) {
        dest[i] = (src[i] >= 'A' && src[i] <= 'Z') ? src[i] + 32 : src[i];
        i++;
    }
    dest[i] = '\0';
}

void calculate_sssa_score(const char *query_str, Document *doc, double *out_score, double *out_base, double *out_pfield) {
    char q_copy[256];
    strncpy(q_copy, query_str, sizeof(q_copy));
    
    char *words[32];
    int word_count = 0;
    char *token = strtok(q_copy, " \t\n");
    while (token != null && word_count < 32) {
        // 小文字化
        for(int i=0; token[i]; i++) {
            if(token[i] >= 'A' && token[i] <= 'Z') token[i] += 32;
        }
        words[word_count++] = token;
        token = strtok(null, " \t\n");
    }

    if (word_count == 0) {
        *out_score = 0.0; *out_base = 0.0; *out_pfield = 0.0;
        return;
    }

    char name_l[128], content_l[256], desc_l[128], all_text[512];
    to_lower_str(name_l, doc->name);
    to_lower_str(content_l, doc->content);
    to_lower_str(desc_l, doc->description);
    snprintf(all_text, sizeof(all_text), "%s %s %s", name_l, content_l, desc_l);

    int matched_words = 0;
    int total_tf = 0;
    for (int i = 0; i < word_count; i++) {
        if (strstr(all_text, words[i]) != null) {
            matched_words++;
        }
        // TFカウント
        const char *tmp = all_text;
        while ((tmp = strstr(tmp, words[i])) != null) {
            total_tf++;
            tmp += strlen(words[i]);
        }
    }

    double match_count_score = (double)matched_words / word_count;
    double term_freq_score = fmin(1.0, log(1.0 + total_tf) / 3.0);
    double base_score = (match_count_score + term_freq_score + doc->context_score) / 3.0;

    int hit_fields = 0;
    char *fields[3] = {name_l, content_l, desc_l};
    for (int f = 0; f < 3; f++) {
        int found_in_field = 0;
        for (int i = 0; i < word_count; i++) {
            if (strstr(fields[f], words[i]) != null) {
                found_in_field = 1;
                break;
            }
        }
        if (found_in_field) hit_fields++;
    }

    double p_field = ((double)hit_fields / 3.0) * 100.0;
    double sssa_score = base_score * (p_field / 100.0);

    *out_score = round(sssa_score * 10000.0) / 10000.0;
    *out_base = round(base_score * 10000.0) / 10000.0;
    *out_pfield = round(p_field * 10.0) / 10.0;
}
