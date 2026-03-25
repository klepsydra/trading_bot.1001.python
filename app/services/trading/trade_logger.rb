# frozen_string_literal: true

require "csv"

module Trading
  class TradeLogger
    FIELDS = %w[
      timestamp base_symbol etf_symbol action
      shares entry_price stop_price take_profit_price
      signal_score z_score rsi_signal ema_signal vol_conf
      portfolio_value order_id
    ].freeze

    def initialize(path = nil)
      @path = path || Rails.root.join("log/trades.csv")
      FileUtils.mkdir_p(File.dirname(@path))
      write_header unless File.exist?(@path)
    end

    def record(**kwargs)
      row = FIELDS.index_with { nil }
      row["timestamp"] = Time.current.utc.iso8601
      row.merge!(stringify_keys(kwargs))
      CSV.open(@path, "a") do |csv|
        csv << FIELDS.map { |f| row[f] }
      end
      Rails.logger.info("TRADE LOGGED | #{row.compact}")
    end

    private

    def write_header
      CSV.open(@path, "w") { |csv| csv << FIELDS }
    end

    def stringify_keys(h)
      h.transform_keys { |k| k.to_s }
    end
  end
end
