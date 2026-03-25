# frozen_string_literal: true

namespace :trading do
  desc "Run one Alpaca momentum iteration (same work as cron)"
  task tick: :environment do
    TradingIterationJob.perform_now
  end
end
