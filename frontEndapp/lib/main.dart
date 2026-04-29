import "package:flutter/material.dart";
import "package:flutter_riverpod/flutter_riverpod.dart";

import "screens/home_screen.dart";

void main() {
  runApp(const ProviderScope(child: MedCiteApp()));
}

class MedCiteApp extends StatelessWidget {
  const MedCiteApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: "MedCite",
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF0284C7)),
        scaffoldBackgroundColor: const Color(0xFFF8FAFC),
        useMaterial3: true,
      ),
      home: const HomeScreen(),
    );
  }
}
