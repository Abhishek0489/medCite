import "package:flutter/material.dart";
import "package:flutter_riverpod/flutter_riverpod.dart";

import "../models/query_response.dart";
import "../state/query_controller.dart";
import "../state/query_state.dart";
import "../widgets/app_widgets.dart";

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  late final TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(queryControllerProvider);
    final notifier = ref.read(queryControllerProvider.notifier);

    if (_controller.text != state.currentQuery) {
      _controller.value = TextEditingValue(
        text: state.currentQuery,
        selection: TextSelection.collapsed(offset: state.currentQuery.length),
      );
    }

    final isBusy = state.phase == QueryPhase.loading || state.phase == QueryPhase.live;

    return Scaffold(
      appBar: AppBar(
        title: const Text("MedCite"),
        actions: <Widget>[
          IconButton(
            tooltip: "Refresh",
            onPressed: notifier.checkHealth,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            BackendStatusChip(healthStatus: state.healthStatus),
            const SizedBox(height: 12),
            TextField(
              controller: _controller,
              minLines: 1,
              maxLines: 3,
              onChanged: notifier.setCurrentQuery,
              decoration: const InputDecoration(
                hintText: "Enter one clinical question...",
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 10),
            Row(
              children: <Widget>[
                FilledButton(
                  onPressed: isBusy
                      ? null
                      : () => notifier.submitLocalQuery(_controller.text),
                  child: const Text("Ask"),
                ),
                const SizedBox(width: 10),
                TextButton(
                  onPressed: isBusy
                      ? null
                      : () {
                          notifier.resetForRephrase();
                          _controller.clear();
                        },
                  child: const Text("Rephrase"),
                ),
              ],
            ),
            const SizedBox(height: 12),
            _HeroQueryChips(
              onSelected: (query) {
                notifier.setCurrentQuery(query);
                notifier.submitLocalQuery(query);
              },
            ),
            const SizedBox(height: 14),
            Expanded(child: _buildStateBody(context, state, notifier)),
          ],
        ),
      ),
    );
  }

  Widget _buildStateBody(
    BuildContext context,
    QueryState state,
    QueryController notifier,
  ) {
    final response = state.response;
    switch (state.phase) {
      case QueryPhase.idle:
        return const Center(
          child: Text("One question, one verified answer. No chat history."),
        );
      case QueryPhase.loading:
        return const Center(child: CircularProgressIndicator());
      case QueryPhase.live:
        return const _LiveProgress();
      case QueryPhase.error:
        return _ErrorPanel(
          message: state.errorMessage ?? "Request failed",
          onRetry: () => notifier.submitLocalQuery(state.submittedQuery),
        );
      case QueryPhase.notFound:
        if (response == null) return const SizedBox.shrink();
        return _NotFoundPanel(
          topSimilarity: response.reasoning.topSimilarity,
          onSearchLive: notifier.submitLiveQuery,
          onRephrase: notifier.resetForRephrase,
        );
      case QueryPhase.abstain:
        if (response == null) return const SizedBox.shrink();
        return _AbstainPanel(
          reason: response.reasoning.verifierUnsupportedClaims.isNotEmpty
              ? response.reasoning.verifierUnsupportedClaims.join("; ")
              : "Confidence below safety threshold",
          onRephrase: notifier.resetForRephrase,
        );
      case QueryPhase.answered:
        if (response == null) return const SizedBox.shrink();
        return _AnswerPanel(response: response);
    }
  }
}

class _HeroQueryChips extends StatelessWidget {
  const _HeroQueryChips({required this.onSelected});
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: QueryController.heroQueries
          .map(
            (query) => ActionChip(
              label: Text(query),
              onPressed: () => onSelected(query),
            ),
          )
          .toList(),
    );
  }
}

class _LiveProgress extends StatelessWidget {
  const _LiveProgress();

  @override
  Widget build(BuildContext context) {
    return const Card(
      child: Padding(
        padding: EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text("Live search in progress"),
            SizedBox(height: 12),
            Text("1. Searching PubMed"),
            Text("2. Synthesizing with Gemini"),
            Text("3. Verifying with Llama"),
          ],
        ),
      ),
    );
  }
}

class _NotFoundPanel extends StatelessWidget {
  const _NotFoundPanel({
    required this.topSimilarity,
    required this.onSearchLive,
    required this.onRephrase,
  });
  final double topSimilarity;
  final VoidCallback onSearchLive;
  final VoidCallback onRephrase;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              "No verified local answer. Top similarity: "
              "${topSimilarity.toStringAsFixed(2)}",
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              children: <Widget>[
                FilledButton(
                  onPressed: onSearchLive,
                  child: const Text("Search live"),
                ),
                OutlinedButton(
                  onPressed: onRephrase,
                  child: const Text("Rephrase"),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _AbstainPanel extends StatelessWidget {
  const _AbstainPanel({required this.reason, required this.onRephrase});
  final String reason;
  final VoidCallback onRephrase;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            const Text(
              "No reliable answer found",
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(reason),
            const SizedBox(height: 8),
            OutlinedButton(
              onPressed: onRephrase,
              child: const Text("Rephrase"),
            ),
          ],
        ),
      ),
    );
  }
}

class _AnswerPanel extends StatelessWidget {
  const _AnswerPanel({required this.response});
  final QueryResponse response;

  @override
  Widget build(BuildContext context) {
    final tierText =
        response.tier == "local" ? "Verified knowledge base" : "Live multi-AI";
    return ListView(
      children: <Widget>[
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(tierText, style: const TextStyle(fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                Text(response.answer),
                const SizedBox(height: 12),
                ConfidenceMeter(confidence: response.confidence),
              ],
            ),
          ),
        ),
        const SizedBox(height: 6),
        ...response.sources.map<Widget>((source) => SourceCard(source: source)),
      ],
    );
  }
}

class _ErrorPanel extends StatelessWidget {
  const _ErrorPanel({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            const Text("Request failed", style: TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text(message),
            const SizedBox(height: 8),
            FilledButton(onPressed: onRetry, child: const Text("Retry")),
          ],
        ),
      ),
    );
  }
}
