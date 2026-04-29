import "../models/query_response.dart";

enum QueryPhase { idle, loading, live, answered, notFound, abstain, error }

class QueryState {
  const QueryState({
    required this.phase,
    required this.currentQuery,
    required this.submittedQuery,
    required this.response,
    required this.errorMessage,
    required this.healthStatus,
  });

  final QueryPhase phase;
  final String currentQuery;
  final String submittedQuery;
  final QueryResponse? response;
  final String? errorMessage;
  final String healthStatus;

  static const QueryState initial = QueryState(
    phase: QueryPhase.idle,
    currentQuery: "",
    submittedQuery: "",
    response: null,
    errorMessage: null,
    healthStatus: "warming",
  );

  QueryState copyWith({
    QueryPhase? phase,
    String? currentQuery,
    String? submittedQuery,
    QueryResponse? response,
    bool clearResponse = false,
    String? errorMessage,
    bool clearError = false,
    String? healthStatus,
  }) {
    return QueryState(
      phase: phase ?? this.phase,
      currentQuery: currentQuery ?? this.currentQuery,
      submittedQuery: submittedQuery ?? this.submittedQuery,
      response: clearResponse ? null : (response ?? this.response),
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      healthStatus: healthStatus ?? this.healthStatus,
    );
  }
}
