/**
 * ReplayController: Centralized state management for timeline replay filters
 * 
 * Handles:
 * - Date range filtering (fromDate, toDate)
 * - Playback speed control (0.25x to 4x)
 * - Vehicle selection filtering
 * - Replay history indexing and filtering
 */

class ReplayController {
  constructor(historyData = []) {
    this.originalHistory = historyData;
    this.filteredHistory = [];
    this.filteredTimestamps = [];
    
    // Filter state
    this.dateFrom = null;
    this.dateTo = null;
    this.selectedVehicles = new Set();
    this.speed = 1;
    
    // Validate speed values
    this.MIN_SPEED = 0.25;
    this.MAX_SPEED = 4;
    this.SPEED_OPTIONS = [0.25, 0.5, 1, 2, 4];
    
    // Initialize with all vehicles selected
    this._populateAvailableVehicles();
  }

  /**
   * Extract unique vehicleIds from history
   */
  _populateAvailableVehicles() {
    const vehicleIds = new Set();
    this.originalHistory.forEach(vehicle => {
      if (vehicle.vehicleId) {
        vehicleIds.add(vehicle.vehicleId);
      }
    });
    this.selectedVehicles = vehicleIds;
  }

  /**
   * Get all available vehicleIds from history
   */
  getAvailableVehicles() {
    const vehicles = [];
    this.originalHistory.forEach(vehicle => {
      if (vehicle.vehicleId && !vehicles.includes(vehicle.vehicleId)) {
        vehicles.push(vehicle.vehicleId);
      }
    });
    return vehicles.sort();
  }

  /**
   * Set date range for filtering
   * @param {string|null} fromDate ISO 8601 date or null
   * @param {string|null} toDate ISO 8601 date or null
   */
  setDateRange(fromDate, toDate) {
    this.dateFrom = fromDate;
    this.dateTo = toDate;
    this._recomputeFiltered();
  }

  /**
   * Set playback speed
   * @param {number} speed Multiplication factor (0.25, 0.5, 1, 2, 4)
   */
  setSpeed(speed) {
    const numSpeed = parseFloat(speed);
    if (!this.SPEED_OPTIONS.includes(numSpeed)) {
      console.warn(`Invalid speed: ${speed}. Must be one of ${this.SPEED_OPTIONS.join(', ')}`);
      return;
    }
    this.speed = numSpeed;
  }

  /**
   * Toggle vehicle selection
   * @param {string} vehicleId Vehicle ID to toggle
   */
  toggleVehicle(vehicleId) {
    if (this.selectedVehicles.has(vehicleId)) {
      this.selectedVehicles.delete(vehicleId);
    } else {
      this.selectedVehicles.add(vehicleId);
    }
    this._recomputeFiltered();
  }

  /**
   * Select specific vehicles
   * @param {string[]} vehicleIds Array of vehicle IDs to select
   */
  setSelectedVehicles(vehicleIds) {
    this.selectedVehicles = new Set(vehicleIds);
    this._recomputeFiltered();
  }

  /**
   * Select all available vehicles
   */
  selectAllVehicles() {
    this._populateAvailableVehicles();
    this._recomputeFiltered();
  }

  /**
   * Deselect all vehicles
   */
  deselectAllVehicles() {
    this.selectedVehicles.clear();
    this._recomputeFiltered();
  }

  /**
   * Check if a vehicle is selected
   */
  isVehicleSelected(vehicleId) {
    return this.selectedVehicles.has(vehicleId);
  }

  /**
   * Get current playback speed
   */
  getSpeed() {
    return this.speed;
  }

  /**
   * Calculate actual replay interval in milliseconds
   * @param {number} baseInterval Base interval (e.g., 1100ms)
   */
  getAdjustedInterval(baseInterval) {
    return baseInterval / this.speed;
  }

  /**
   * Filter timestamp by date range
   */
  _isTimestampInRange(timestamp) {
    if (!timestamp) return false;
    
    const ts = new Date(timestamp).getTime();
    
    if (this.dateFrom) {
      const from = new Date(this.dateFrom + 'T00:00:00Z').getTime();
      if (ts < from) return false;
    }
    
    if (this.dateTo) {
      const to = new Date(this.dateTo + 'T23:59:59Z').getTime();
      if (ts > to) return false;
    }
    
    return true;
  }

  /**
   * Recompute filtered history based on current filters
   */
  _recomputeFiltered() {
    this.filteredHistory = [];
    const timestampSet = new Set();

    // Filter by selected vehicles and date range
    this.originalHistory.forEach(vehicle => {
      if (!this.selectedVehicles.has(vehicle.vehicleId)) {
        return; // Skip unselected vehicles
      }

      const filteredRecords = vehicle.history.filter(record =>
        this._isTimestampInRange(record.timestamp)
      );

      if (filteredRecords.length > 0) {
        this.filteredHistory.push({
          ...vehicle,
          history: filteredRecords
        });

        // Collect unique timestamps
        filteredRecords.forEach(record => {
          if (record.timestamp) {
            timestampSet.add(record.timestamp);
          }
        });
      }
    });

    // Sort timestamps chronologically
    this.filteredTimestamps = Array.from(timestampSet).sort();
  }

  /**
   * Get filtered history data
   */
  getFilteredHistory() {
    return this.filteredHistory;
  }

  /**
   * Get filtered timestamps (chronologically sorted)
   */
  getFilteredTimestamps() {
    return this.filteredTimestamps;
  }

  /**
   * Get total number of filtered vehicles
   */
  getFilteredVehicleCount() {
    return this.filteredHistory.length;
  }

  /**
   * Get date range boundaries from filtered data
   */
  getDateRangeBoundaries() {
    if (this.filteredTimestamps.length === 0) {
      return { start: null, end: null };
    }

    return {
      start: this.filteredTimestamps[0],
      end: this.filteredTimestamps[this.filteredTimestamps.length - 1]
    };
  }

  /**
   * Get current filter state
   */
  getFilterState() {
    return {
      dateFrom: this.dateFrom,
      dateTo: this.dateTo,
      speed: this.speed,
      selectedVehicles: Array.from(this.selectedVehicles),
      filteredVehicleCount: this.getFilteredVehicleCount(),
      filteredTimestampCount: this.filteredTimestamps.length
    };
  }

  /**
   * Reset all filters to default state
   */
  reset() {
    this.dateFrom = null;
    this.dateTo = null;
    this.speed = 1;
    this._populateAvailableVehicles();
    this._recomputeFiltered();
  }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = ReplayController;
}

if (typeof window !== 'undefined') {
  window.ReplayController = ReplayController;
}
