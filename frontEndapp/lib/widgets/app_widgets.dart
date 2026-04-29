import "package:flutter/material.dart";
import "package:url_launcher/url_launcher.dart";

import "../models/query_response.dart";

class BackendStatusChip extends StatelessWidget {
  const BackendStatusChip({required this.healthStatus, super.key});
  final String healthStatus;

  @override
  Widget build(BuildContext context) {
    late final Color bg;
    late final Color fg;
    late final String label;
    switch (healthStatus) {
      case "online":
        bg = const Color(0xFFDCFCE7);
        fg = const Color(0xFF166534);
        label = "Backend online";
      case "warming":
        bg = const Color(0xFFE2E8F0);
        fg = const Color(0xFF334155);
        label = "Backend warming";
      default:
        bg = const Color(0xFFFFE4E6);
        fg = const Color(0xFF9F1239);
        label = "Backend offline";
    }

    return Chip(
      backgroundColor: bg,
      label: Text(label, style: TextStyle(color: fg)),
      avatar: CircleAvatar(backgroundColor: fg, radius: 4),
    );
  }
}

class ConfidenceMeter extends StatelessWidget {
  const ConfidenceMeter({required this.confidence, super.key});
  final double confidence;

  @override
  Widget build(BuildContext context) {
    final value = confidence.clamp(0, 1).toDouble();
    final color = value >= 0.85
        ? Colors.green
        : value >= 0.75
            ? Colors.orange
            : Colors.red;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text("Confidence ${(value * 100).toStringAsFixed(0)}%"),
        const SizedBox(height: 6),
        LinearProgressIndicator(
          value: value,
          minHeight: 10,
          borderRadius: BorderRadius.circular(8),
          color: color,
          backgroundColor: Colors.grey.shade300,
        ),
      ],
    );
  }
}

class SourceCard extends StatelessWidget {
  const SourceCard({required this.source, super.key});
  final SourceItem source;

  Future<void> _openLink(String url) async {
    final uri = Uri.tryParse(url);
    if (uri == null) {
      return;
    }
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 6),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              "[${source.citationNumber}] ${source.title}",
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 4),
            Text(
              "${source.journal} · ${source.year} · ${source.publicationType}",
              style: TextStyle(color: Colors.grey.shade700, fontSize: 12),
            ),
            if (source.authors.isNotEmpty) ...<Widget>[
              const SizedBox(height: 4),
              Text(
                source.authors,
                style: TextStyle(color: Colors.grey.shade700, fontSize: 12),
              ),
            ],
            const SizedBox(height: 8),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: const Color(0xFFF8FAFC),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(source.quotedPassage),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: <Widget>[
                OutlinedButton(
                  onPressed: source.url.isEmpty ? null : () => _openLink(source.url),
                  child: const Text("PubMed"),
                ),
                OutlinedButton(
                  onPressed:
                      source.doiUrl.isEmpty ? null : () => _openLink(source.doiUrl),
                  child: const Text("DOI"),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
