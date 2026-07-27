<?php
function calculateSssaScore($queryStr, $doc) {
    $queryWords = array_filter(array_map('trim', explode(' ', strtolower($queryStr))));
    if (empty($queryWords)) {
        return [0.0, 0.0, 0.0];
    }

    $nameTxt = strtolower($doc['name']);
    $contentTxt = strtolower($doc['content']);
    $descTxt = strtolower($doc['description']);
    $allText = "$nameTxt $contentTxt $descTxt";

    $matchedWords = 0;
    foreach ($queryWords as $w) {
        if (strpos($allText, $w) !== false) $matchedWords++;
    }
    $matchCountScore = $matchedWords / count($queryWords);

    $totalTf = 0;
    foreach ($queryWords as $w) {
        $totalTf += substr_count($allText, $w);
    }
    $termFreqScore = min(1.0, log(1 + $totalTf) / 3.0);
    $contextScore = $doc['context_score'] ?? 0.5;

    $baseScore = ($matchCountScore + $termFreqScore + $contextScore) / 3.0;

    $fields = [$nameTxt, $contentTxt, $descTxt];
    $hitFields = 0;
    foreach ($fields as $f) {
        foreach ($queryWords as $w) {
            if (strpos($f, $w) !== false) {
                $hitFields++;
                break;
            }
        }
    }
    $pField = ($hitFields / count($fields)) * 100.0;
    $sssaScore = $baseScore * ($pField / 100.0);

    return [
        round($sssaScore, 4),
        round($baseScore, 4),
        round($pField, 1)
    ];
}

function partitionInto10Buckets(&$activeItems) {
    $buckets = array_fill(0, 10, []);
    foreach ($activeItems as $item) {
        $compScore = $item['score'] * 0.7 + $item['base'] * 0.3;
        $bIdx = (int)((1.0 - min(1.0, max(0.0, $compScore))) * 10);
        if ($bIdx >= 10) $bIdx = 9;
        $buckets[$bIdx][] = $item;
    }

    $partitioned = [];
    foreach ($buckets as &$b) {
        shuffle($b);
        $partitioned = array_merge($partitioned, $b);
    }
    return $partitioned;
}
