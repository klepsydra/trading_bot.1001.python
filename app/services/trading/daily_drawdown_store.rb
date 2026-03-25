# frozen_string_literal: true

require "json"

module Trading
  # Persists start-of-day portfolio value (process may restart; in-memory was not enough).
  class DailyDrawdownStore
    def initialize(path = nil)
      @path = path || Rails.root.join("tmp/trading/day_start_portfolio.json")
    end

    def refresh_start_of_day!(portfolio_value)
      FileUtils.mkdir_p(File.dirname(@path))
      today = Time.zone.today.iso8601
      data = read_file
      if data["date"] != today
        data = { "date" => today, "value" => portfolio_value.to_f }
        File.write(@path, JSON.generate(data))
        Rails.logger.info("Day start portfolio value: $#{format('%.2f', portfolio_value)}")
      end
      data
    end

    def start_of_day_value
      data = read_file
      return nil if data["value"].nil?

      data["value"].to_f
    end

    def start_date
      read_file["date"]
    end

    private

    def read_file
      return {} unless File.exist?(@path)

      JSON.parse(File.read(@path))
    rescue JSON::ParserError
      {}
    end
  end
end
