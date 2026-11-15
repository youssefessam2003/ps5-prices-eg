import 'package:flutter/material.dart';

import 'data/repo.dart';
import 'ui/home_page.dart';
import 'ui/offers_page.dart';
import 'ui/stores_page.dart';
import 'ui/theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  final repo = Repo()..init();
  runApp(Ps5PricesApp(repo: repo));
}

class Ps5PricesApp extends StatelessWidget {
  final Repo repo;
  const Ps5PricesApp({super.key, required this.repo});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'PS5 Prices EG',
        debugShowCheckedModeBanner: false,
        theme: buildTheme(),
        home: Shell(repo: repo),
      );
}

class Shell extends StatefulWidget {
  final Repo repo;
  const Shell({super.key, required this.repo});

  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> {
  int tab = 0;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.repo,
      builder: (context, _) {
        final pages = [
          HomePage(repo: widget.repo, onSeeAll: () => setState(() => tab = 1)),
          OffersPage(repo: widget.repo),
          StoresPage(repo: widget.repo),
        ];
        return Scaffold(
          body: SafeArea(bottom: false, child: IndexedStack(index: tab, children: pages)),
          floatingActionButton: tab == 2
              ? FloatingActionButton.extended(
                  onPressed: () => showLogSheet(context, widget.repo),
                  icon: const Icon(Icons.add_rounded),
                  label: const Text('Log a price'),
                )
              : null,
          bottomNavigationBar: NavigationBar(
            selectedIndex: tab,
            onDestinationSelected: (i) => setState(() => tab = i),
            destinations: const [
              NavigationDestination(icon: Icon(Icons.space_dashboard_outlined), selectedIcon: Icon(Icons.space_dashboard_rounded), label: 'Overview'),
              NavigationDestination(icon: Icon(Icons.local_offer_outlined), selectedIcon: Icon(Icons.local_offer_rounded), label: 'Offers'),
              NavigationDestination(icon: Icon(Icons.storefront_outlined), selectedIcon: Icon(Icons.storefront_rounded), label: 'Stores'),
            ],
          ),
        );
      },
    );
  }
}
