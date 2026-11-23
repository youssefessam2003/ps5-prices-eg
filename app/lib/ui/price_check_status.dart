import 'package:flutter/material.dart';

import '../data/repo.dart';
import 'theme.dart';

class RefreshPricesButton extends StatelessWidget {
  final Repo repo;
  const RefreshPricesButton({super.key, required this.repo});

  @override
  Widget build(BuildContext context) => IconButton(
    tooltip: repo.loading ? 'Price check in progress' : 'Search stores again',
    onPressed: repo.loading ? null : repo.refresh,
    icon: const Icon(Icons.refresh_rounded),
  );
}

class PriceCheckStatus extends StatelessWidget {
  final Repo repo;
  const PriceCheckStatus({super.key, required this.repo});

  @override
  Widget build(BuildContext context) {
    final check = repo.priceCheck;
    if (!repo.loading && repo.error == null && check == null) {
      return const SizedBox.shrink();
    }
    final title = repo.error != null
        ? 'Price check needs attention'
        : repo.loading
        ? check?.running == true
              ? 'Searching stores again…'
              : 'Updating prices…'
        : 'Latest price check';
    final details =
        repo.error ?? check?.summary ?? 'Loading the latest verified prices.';
    return Semantics(
      liveRegion: true,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Palette.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: repo.error == null ? Palette.line : Palette.amber,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 6),
            Text(
              details,
              style: const TextStyle(
                color: Palette.muted,
                fontSize: 12.5,
                height: 1.4,
              ),
            ),
            if (repo.loading) ...[
              const SizedBox(height: 12),
              LinearProgressIndicator(
                value: check?.running == true ? check!.progress : null,
                color: Palette.cyan,
                backgroundColor: Palette.line,
                borderRadius: BorderRadius.circular(4),
              semanticsLabel: check?.running == true
                  ? 'Price search progress, ${check!.completed} of ${check.total} sources'
                  : 'Price search progress',
                semanticsValue: check?.running == true
                  ? '${(check!.progress! * 100).round()}%'
                    : null,
              ),
              const SizedBox(height: 8),
              const Text(
                'Previous prices stay visible until the check finishes.',
                style: TextStyle(color: Palette.muted, fontSize: 12),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
