using System;
using System.Collections.Generic;
using System.Linq;

public class Document
{
    public string Id { get; set; }
    public string Name { get; set; }
    public string Content { get; set; }
    public string Description { get; set; }
    public double ContextScore { get; set; }
}

public class ActiveItem
{
    public Document Doc { get; set; }
    public double Score { get; set; }
    public double Base { get; set; }
    public double PField { get; set; }
    public bool Locked { get; set; }
}

public class SSSASorter
{
    public static (double score, double baseScore, double pField) CalculateSssaScore(string queryStr, Document doc)
    {
        var queryWords = queryStr.ToLower().Split(new[] { ' ', '\t', '\n' }, StringSplitOptions.RemoveEmptyEntries);
        if (queryWords.Length == 0) return (0.0, 0.0, 0.0);

        string nameTxt = doc.Name.ToLower();
        string contentTxt = doc.Content.ToLower();
        string descTxt = doc.Description.ToLower();
        string allText = $"{nameTxt} {contentTxt} {descTxt}";

        int matchedWords = queryWords.Count(w => allText.Contains(w));
        double matchCountScore = (double)matchedWords / queryWords.Length;

        int totalTf = queryWords.Sum(w => {
            int count = 0, idx = 0;
            while ((idx = allText.IndexOf(w, idx)) != -1)
            {
                count++;
                idx += w.Length;
            }
            return count;
        });

        double termFreqScore = Math.Min(1.0, Math.Log(1.0 + totalTf) / 3.0);
        double baseScore = (matchCountScore + termFreqScore + doc.ContextScore) / 3.0;

        string[] fields = { nameTxt, contentTxt, descTxt };
        int hitFields = fields.Count(f => queryWords.Any(w => f.Contains(w)));
        double pField = ((double)hitFields / fields.Length) * 100.0;
        double sssaScore = baseScore * (pField / 100.0);

        return (
            Math.Round(sssaScore, 4),
            Math.Round(baseScore, 4),
            Math.Round(pField, 1)
        );
    }

    public static List<ActiveItem> PartitionInto10Buckets(List<ActiveItem> activeItems)
    {
        var buckets = Enumerable.Range(0, 10).Select(_ => new List<ActiveItem>()).ToArray();
        foreach (var item in activeItems)
        {
            double compScore = item.Score * 0.7 + item.Base * 0.3;
            int bIdx = (int)((1.0 - Math.Min(1.0, Math.Max(0.0, compScore))) * 10);
            if (bIdx >= 10) bIdx = 9;
            buckets[bIdx].Add(item);
        }

        var rnd = new Random();
        var partitioned = new List<ActiveItem>();
        foreach (var b in buckets)
        {
            var shuffled = b.OrderBy(_ => rnd.Next()).ToList();
            partitioned.AddRange(shuffled);
        }
        return partitioned;
    }
}
