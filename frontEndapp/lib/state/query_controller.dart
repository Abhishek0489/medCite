import "package:flutter_riverpod/flutter_riverpod.dart";

import "../models/query_response.dart";
import "../services/api_service.dart";
import "query_state.dart";

final apiServiceProvider = Provider<ApiService>((ref) => ApiService());

final queryControllerProvider =
    StateNotifierProvider<QueryController, QueryState>(
  (ref) => QueryController(ref.read(apiServiceProvider)),
);

class QueryController extends StateNotifier<QueryState> {
  QueryController(this._apiService) : super(QueryState.initial) {
    checkHealth();
  }

  final ApiService _apiService;

  static const List<String> heroQueries = <String>[
    "Does empagliflozin reduce cardiovascular mortality in HFpEF?",
    "First-line treatment for drug-resistant tuberculosis 2024",
    "Levetiracetam status epilepticus dose",
    "Is acetaminophen safe in third trimester pregnancy?",
    "Side effects of SGLT2 inhibitors in elderly patients",
  ];

  Future<void> checkHealth() async {
    state = state.copyWith(healthStatus: "warming");
    final health = await _apiService.checkHealth();
    state = state.copyWith(healthStatus: health.status);
  }

  Future<void> submitLocalQuery(String query) async {
    final trimmed = query.trim();
    if (trimmed.length < 3) {
      state = state.copyWith(
        phase: QueryPhase.error,
        errorMessage: "Please enter at least 3 characters.",
      );
      return;
    }

    state = state.copyWith(
      currentQuery: trimmed,
      submittedQuery: trimmed,
      phase: QueryPhase.loading,
      clearResponse: true,
      clearError: true,
    );

    try {
      final response = await _apiService.queryLocal(trimmed);
      _applyResponse(response);
    } catch (error) {
      state = state.copyWith(
        phase: QueryPhase.error,
        errorMessage: error.toString(),
      );
    }
  }

  Future<void> submitLiveQuery() async {
    if (state.submittedQuery.isEmpty) {
      return;
    }

    state = state.copyWith(
      phase: QueryPhase.live,
      clearResponse: true,
      clearError: true,
    );

    try {
      final response = await _apiService.queryLive(state.submittedQuery);
      _applyResponse(response);
    } catch (error) {
      state = state.copyWith(
        phase: QueryPhase.error,
        errorMessage: error.toString(),
      );
    }
  }

  void resetForRephrase() {
    state = state.copyWith(
      phase: QueryPhase.idle,
      clearResponse: true,
      clearError: true,
    );
  }

  void setCurrentQuery(String value) {
    state = state.copyWith(currentQuery: value);
  }

  void _applyResponse(QueryResponse response) {
    QueryPhase phase;
    if (response.status == "found") {
      phase = QueryPhase.answered;
    } else if (response.status == "not_found") {
      phase = QueryPhase.notFound;
    } else if (response.status == "insufficient_evidence") {
      phase = QueryPhase.abstain;
    } else {
      phase = QueryPhase.error;
    }

    state = state.copyWith(
      response: response,
      phase: phase,
      clearError: true,
    );
  }
}
