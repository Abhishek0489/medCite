class QueryResponse {
  QueryResponse({
    required this.status,
    required this.tier,
    required this.answer,
    required this.confidence,
    required this.sources,
    required this.reasoning,
  });

  final String status;
  final String tier;
  final String answer;
  final double confidence;
  final List<SourceItem> sources;
  final Reasoning reasoning;

  factory QueryResponse.fromJson(Map<String, dynamic> json) {
    return QueryResponse(
      status: (json["status"] ?? "").toString(),
      tier: (json["tier"] ?? "").toString(),
      answer: (json["answer"] ?? "").toString(),
      confidence: (json["confidence"] as num?)?.toDouble() ?? 0,
      sources: (json["sources"] as List<dynamic>? ?? const <dynamic>[])
          .map((item) => SourceItem.fromJson(item as Map<String, dynamic>))
          .toList(),
      reasoning: Reasoning.fromJson(
        json["reasoning"] as Map<String, dynamic>? ?? const <String, dynamic>{},
      ),
    );
  }
}

class SourceItem {
  SourceItem({
    required this.citationNumber,
    required this.title,
    required this.journal,
    required this.year,
    required this.authors,
    required this.publicationType,
    required this.url,
    required this.doiUrl,
    required this.quotedPassage,
  });

  final int citationNumber;
  final String title;
  final String journal;
  final String year;
  final String authors;
  final String publicationType;
  final String url;
  final String doiUrl;
  final String quotedPassage;

  factory SourceItem.fromJson(Map<String, dynamic> json) {
    return SourceItem(
      citationNumber: (json["citation_number"] as num?)?.toInt() ?? 0,
      title: (json["title"] ?? "").toString(),
      journal: (json["journal"] ?? "").toString(),
      year: (json["year"] ?? "").toString(),
      authors: (json["authors"] ?? "").toString(),
      publicationType: (json["publication_type"] ?? "").toString(),
      url: (json["url"] ?? "").toString(),
      doiUrl: (json["doi_url"] ?? "").toString(),
      quotedPassage: (json["quoted_passage"] ?? "").toString(),
    );
  }
}

class Reasoning {
  Reasoning({
    required this.queriesSearched,
    required this.topSimilarity,
    required this.verifierUnsupportedClaims,
    required this.articlesAddedToKb,
    required this.writeBackError,
  });

  final List<String> queriesSearched;
  final double topSimilarity;
  final List<String> verifierUnsupportedClaims;
  final int? articlesAddedToKb;
  final String? writeBackError;

  factory Reasoning.fromJson(Map<String, dynamic> json) {
    return Reasoning(
      queriesSearched: (json["queries_searched"] as List<dynamic>? ?? const [])
          .map((item) => item.toString())
          .toList(),
      topSimilarity: (json["top_similarity"] as num?)?.toDouble() ?? 0,
      verifierUnsupportedClaims:
          (json["verifier_unsupported_claims"] as List<dynamic>? ?? const [])
              .map((item) => item.toString())
              .toList(),
      articlesAddedToKb: (json["articles_added_to_kb"] as num?)?.toInt(),
      writeBackError: json["write_back_error"]?.toString(),
    );
  }
}

class HealthResponse {
  HealthResponse({required this.status, required this.message});

  final String status;
  final String message;

  factory HealthResponse.fromJson(Map<String, dynamic> json) {
    final status = (json["status"] ?? "").toString();
    if (status == "ok") {
      return HealthResponse(status: "online", message: "Backend online");
    }
    return HealthResponse(status: "offline", message: "Backend offline");
  }
}
