// ==========================================
// 1. SSSA スコア & カバー率計算
// ==========================================
function calculateSssaScore(queryStr, doc) {
    const queryWords = queryStr.toLowerCase().split(/\s+/).filter(w => w.length > 0);
    if (queryWords.length === 0) return [0.0, 0.0, 0.0];

    const nameTxt = doc.name.toLowerCase();
    const contentTxt = doc.content.toLowerCase();
    const descTxt = doc.description.toLowerCase();

    // ① キーワード一致数
    const allText = `${nameTxt} ${contentTxt} ${descTxt}`;
    let matchedWords = 0;
    queryWords.forEach(w => {
        if (allText.includes(w)) matchedWords++;
    });
    const matchCountScore = matchedWords / queryWords.length;

    // ② キーワード出現数 (TF)
    let totalTf = 0;
    queryWords.forEach(w => {
        const regex = new RegExp(w, 'g');
        const matches = allText.match(regex);
        if (matches) totalTf += matches.length;
    });
    const termFreqScore = Math.min(1.0, Math.log1p(totalTf) / 3.0);
    
    // ③ 類語・文脈スコア
    const contextScore = doc.context_score || 0.5;

    const baseScore = (matchCountScore + termFreqScore + contextScore) / 3.0;

    // ④ カバー率
    const fields = [nameTxt, contentTxt, descTxt];
    let hitFields = 0;
    fields.forEach(f => {
        if (queryWords.some(w => f.includes(w))) hitFields++;
    });
    const pField = (hitFields / fields.length) * 100.0;
    const sssaScore = baseScore * (pField / 100.0);

    return [
        Math.round(sssaScore * 10000) / 10000,
        Math.round(baseScore * 10000) / 10000,
        Math.round(pField * 10) / 10
    ];
}


// ==========================================
// 2. 10区分分けアルゴリズム
// ==========================================
function partitionInto10Buckets(activeItems) {
    const buckets = Array.from({length: 10}, () => []);
    
    activeItems.forEach(item => {
        // SSSAスコア70% + 基本スコア30% の複合スコアでバケット配置
        const compScore = item.score * 0.7 + item.base * 0.3;
        let bIdx = Math.floor((1.0 - Math.min(1.0, Math.max(0.0, compScore))) * 10);
        if (bIdx >= 10) bIdx = 9;
        buckets[bIdx].push(item);
    });

    let partitioned = [];
    buckets.forEach(b => {
        // Fisher-Yates シャッフル
        for (let i = b.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [b[i], b[j]] = [b[j], b[i]];
        }
        partitioned = partitioned.concat(b);
    });
    return partitioned;
}


// ==========================================
// 3. カスタム・アニメーション・ソート
// ==========================================
function customSortStep(activeItems, stepState) {
    const n = activeItems.length;
    const concurrentCount = Math.max(1, 1 + Math.floor(n / 10));
    let activeIndices = [];
    let processed = 0;

    // 部分的・段階的な比較・スワップ処理
    while (stepState.currIdx < n - 1 && processed < concurrentCount) {
        let i = stepState.currIdx;
        stepState.currIdx++;

        let maxJ = Math.min(n, i + 6);
        for (let j = i + 1; j < maxJ; j++) {
            activeIndices.push(i, j);

            let leftKey = [activeItems[i].score, activeItems[i].base];
            let rightKey = [activeItems[j].score, activeItems[j].base];

            // 降順ソート条件（左 < 右 ならスワップ）
            if (leftKey[0] < rightKey[0] || (leftKey[0] === rightKey[0] && leftKey[1] < rightKey[1])) {
                activeItems[i].locked = false;
                activeItems[j].locked = false;

                let temp = activeItems[i];
                activeItems[i] = activeItems[j];
                activeItems[j] = temp;

                stepState.totalSwaps++;
                processed++;
                break;
            }
        }
    }

    // パス完了時の確定判定ロジック
    if (stepState.currIdx >= n - 1) {
        stepState.currIdx = 0;
        stepState.pass++;

        for (let i = 0; i < n; i++) {
            let minK = Math.max(0, i - 25);
            let maxK = Math.min(n, i + 26);
            let keyI = [activeItems[i].score, activeItems[i].base];

            let hasError = false;
            for (let k = minK; k < maxK; k++) {
                let keyK = [activeItems[k].score, activeItems[k].base];
                if (k < i && (keyK[0] < keyI[0] || (keyK[0] === keyI[0] && keyK[1] < keyI[1]))) {
                    hasError = true;
                    break;
                }
                if (k > i && (keyK[0] > keyI[0] || (keyK[0] === keyI[0] && keyK[1] > keyI[1]))) {
                    hasError = true;
                    break;
                }
            }
            activeItems[i].locked = !hasError;
        }
    }

    return activeIndices;
}
