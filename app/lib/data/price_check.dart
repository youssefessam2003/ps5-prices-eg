class PriceCheck {
  final String id, status;
  final int completed, total, succeeded, failed;
  final String? currentSource, error;

  PriceCheck.fromJson(Map<String, dynamic> json)
    : id = json['id'],
      status = json['status'],
      completed = json['completed'] ?? 0,
      total = json['total'] ?? 0,
      succeeded = json['succeeded'] ?? 0,
      failed = json['failed'] ?? 0,
      currentSource = json['current_source'],
      error = json['error'];

  bool get running => status == 'running';
  bool get successful => status == 'completed';
  double? get progress =>
      total == 0 ? null : (completed / total).clamp(0, 1).toDouble();

  String get summary => running
      ? '$completed/$total sources checked${currentSource == null ? '' : ' · $currentSource'}'
      : successful
      ? 'Fresh check complete · $succeeded/$total sources verified${failed == 0 ? '' : ' · $failed unavailable'}'
      : error ?? 'The price check did not finish. Please retry.';
}
