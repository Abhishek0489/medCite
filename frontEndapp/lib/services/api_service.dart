import "package:dio/dio.dart";

import "../models/query_response.dart";
import "app_config.dart";

class ApiService {
  ApiService()
      : _dio = Dio(
          BaseOptions(
            baseUrl: AppConfig.backendBaseUrl,
            connectTimeout: const Duration(seconds: 10),
            receiveTimeout: const Duration(seconds: 30),
            sendTimeout: const Duration(seconds: 10),
            contentType: Headers.jsonContentType,
          ),
        );

  final Dio _dio;

  Future<HealthResponse> checkHealth() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>("/health");
      return HealthResponse.fromJson(response.data ?? const {});
    } on DioException catch (_) {
      return HealthResponse(status: "offline", message: "Backend offline");
    }
  }

  Future<QueryResponse> queryLocal(String query) async {
    return _postQuery("/query/local", query);
  }

  Future<QueryResponse> queryLive(String query) async {
    return _postQuery("/query/live", query);
  }

  Future<QueryResponse> _postQuery(String path, String query) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        path,
        data: <String, dynamic>{"query": query},
      );
      return QueryResponse.fromJson(response.data ?? const {});
    } on DioException catch (error) {
      final detail = error.response?.data;
      final detailText = detail is Map<String, dynamic>
          ? (detail["detail"] ?? "Request failed").toString()
          : "Request failed";
      throw ApiException(detailText);
    } catch (_) {
      throw ApiException("Unexpected error while contacting backend");
    }
  }
}

class ApiException implements Exception {
  ApiException(this.message);
  final String message;

  @override
  String toString() => message;
}
