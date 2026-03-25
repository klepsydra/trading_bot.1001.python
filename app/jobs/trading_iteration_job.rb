# frozen_string_literal: true

class TradingIterationJob < ApplicationJob
  queue_as :default

  def perform
    Trading::Runner.new.tick
  end
end
