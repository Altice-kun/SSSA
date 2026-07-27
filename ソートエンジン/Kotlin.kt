import kotlin.math.*

data class Document(
    val id: String,
    val name: String,
    val content: String,
    val description: String,
    val contextScore: Double
)

data class ActiveItem(
    val doc: Document,
    var score: Double,
    var base: Double,
    var pField: Double,
    var locked: Boolean
)

fun calculateSssaScore(queryStr: String, doc: Document): Triple<Double, Double, Double> {
    val queryWords = queryStr.lowercase().split(Regex("\\s+")).filter { it.isNotBlank() }
    if (queryWords.isEmpty()) return Triple(0.0, 0.0, 0.0)

    val nameTxt = doc.name.lowercase()
    val contentTxt = doc.content.lowercase()
    val descTxt = doc.description.lowercase()
    val allText = "$nameTxt $contentTxt $descTxt"

    val matchedWords = queryWords.count { allText.contains(it) }
    val matchCountScore = matchedWords.toDouble() / queryWords.size

    val totalTf = queryWords.sumOf { w ->
        w.toRegex().findAll(allText).count()
    }

    val termFreqScore = min(1.0, ln(1.0 + totalTf) / 3.0)
    val baseScore = (matchCountScore + termFreqScore + doc.contextScore) / 3.0

    val fields = listOf(nameTxt, contentTxt, descTxt)
    val hitFields = fields.count { f -> queryWords.any { f.contains(it) } }
    val pField = (hitFields.toDouble() / fields.size) * 100.0
    val sssaScore = baseScore * (pField / 100.0)

    return Triple(
        round(sssaScore * 10000) / 10000,
        round(baseScore * 10000) / 10000,
        round(pField * 10) / 10
    )
}

fun partitionInto10Buckets(activeItems: List<ActiveItem>): List<ActiveItem> {
    val buckets = Array(10) { mutableListOf<ActiveItem>() }
    for (item in activeItems) {
        val compScore = item.score * 0.7 + item.base * 0.3
        var bIdx = ((1.0 - min(1.0, max(0.0, compScore))) * 10).toInt()
        if (bIdx >= 10) bIdx = 9
        buckets[bIdx].add(item)
    }

    val partitioned = mutableListOf<ActiveItem>()
    for (b in buckets) {
        b.shuffle()
        partitioned.addAll(b)
    }
    return partitioned
}
