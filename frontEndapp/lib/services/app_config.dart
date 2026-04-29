class AppConfig {
  AppConfig._();

  static const String localBaseUrl = "http://localhost:8000";
  static const String prodBaseUrl = "https://Tony0489-MedCite-api.hf.space";

  static const String backendBaseUrl = String.fromEnvironment(
    "MEDCITE_BASE_URL",
    defaultValue: localBaseUrl,
  );
}
