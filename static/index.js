const investments = [];
let four01kData = {};
let expandedInvestmentId = null; // State to keep track of which investment's details are currently expanded
let currentSortCriteria = "symbol"; // Default sort criteria
let currentSortDirection = "asc"; // Default sort direction (ascending)
let isSortDropdownOpen = false; // State for dropdown visibility
let isGainViewDropdownOpen = false; // State for gain view dropdown visibility
let debounceTimer; // For symbol input debounce
let selectedSymbolData = null; // Stores the full data of the selected symbol from suggestions
let currentGainView = "day"; // 'day' or 'total'

/**
 * Toggles the expansion of an investment card.
 * @param {string} id - The ID of the investment to toggle.
 */
function toggleExpand(id) {
  const currentExpanded = expandedInvestmentId;
  // If the clicked card is already expanded, collapse it. Otherwise, expand the clicked card.
  expandedInvestmentId = currentExpanded === id ? null : id;
  renderInvestments(); // Re-render the list to reflect the change
}

/**
 * Helper function to format currency.
 * @param {number} value - The numerical value to format.
 * @returns {string} The formatted currency string.
 */
function formatCurrency(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(value);
}

/**
 * Helper function to format percentage.
 * @param {number} value - The numerical value to format.
 * @returns {string} The formatted percentage string.
 */
function formatPercentage(value) {
  return `${value.toFixed(2)} %`;
}

/**
 * Determines the Tailwind CSS class for text color based on a numerical value.
 * @param {number} value - The numerical value (e.g., gain/loss).
 * @returns {string} The Tailwind CSS class for text color.
 */
function getChangeStyle(value) {
  if (value > 0) {
    return "text-green-600"; // Green for positive
  } else if (value < 0) {
    return "text-red-600"; // Red for negative
  }
  return "text-gray-800"; // Default for zero or no change
}

/**
 * Determines the arrow icon based on a numerical value.
 * @param {number} value - The numerical value (e.g., gain/loss percentage).
 * @returns {string} The arrow icon character (↑ or ↓).
 */
function getArrowIcon(value) {
  if (value > 0) {
    return "🡹"; // Up arrow for positive
  } else if (value < 0) {
    return "🡻"; // Down arrow for negative
  }
  return ""; // No arrow for zero or no change
}

/**
 * Toggles the visibility of the sort dropdown menu.
 */
function toggleSortDropdown() {
  isSortDropdownOpen = !isSortDropdownOpen;
  const dropdownMenu = document.getElementById("sort-dropdown-menu");
  const sortArrow = document.getElementById("sort-arrow");
  if (isSortDropdownOpen) {
    dropdownMenu.classList.remove("hidden");
    sortArrow.classList.add("rotate-180");
  } else {
    dropdownMenu.classList.add("hidden");
    sortArrow.classList.remove("rotate-180");
  }
}

/**
 * Toggles the visibility of the gain view dropdown menu.
 */
function toggleGainViewDropdown() {
  isGainViewDropdownOpen = !isGainViewDropdownOpen;
  const dropdownMenu = document.getElementById("gain-view-dropdown-menu");
  const gainViewArrow = document.getElementById("gain-view-arrow");
  if (isGainViewDropdownOpen) {
    dropdownMenu.classList.remove("hidden");
    gainViewArrow.classList.add("rotate-180");
  } else {
    dropdownMenu.classList.add("hidden");
    gainViewArrow.classList.remove("rotate-180");
  }
}

/**
 * Sets the current gain view type ('day' or 'total') and re-renders.
 * @param {string} type - The type of gain to display ('day' or 'total').
 */
function setGainView(type) {
  currentGainView = type;
  const gainHeaderText = document.getElementById("gain-header-text");

  if (currentGainView === "day") {
    gainHeaderText.textContent = "Day Gain";
  } else {
    gainHeaderText.textContent = "Total Gain";
  }
  toggleGainViewDropdown(); // Close the dropdown after selection
  renderInvestments(); // Re-render to reflect the new view
}

/**
 * Sorts the investments array based on the given criteria and updates the display.
 * @param {string} criteria - The property to sort by (e.g., 'symbol', 'price').
 */
function sortInvestments(criteria) {
  if (currentSortCriteria === criteria) {
    // If the same criteria is clicked, toggle sort direction
    currentSortDirection = currentSortDirection === "asc" ? "desc" : "asc";
  } else {
    // If a new criteria is clicked, set it and default to ascending
    currentSortCriteria = criteria;
    currentSortDirection = "asc";
  }

  // Sort the investments array
  investments.sort((a, b) => {
    let valA = a[currentSortCriteria];
    let valB = b[currentSortCriteria];

    // Handle string comparison for symbol
    if (typeof valA === "string" && typeof valB === "string") {
      return currentSortDirection === "asc"
        ? valA.localeCompare(valB)
        : valB.localeCompare(valA);
    }
    // Handle numerical comparison for other criteria
    return currentSortDirection === "asc" ? valA - valB : valB - valA;
  });

  // Update the sort button text
  const sortCriteriaText = document.getElementById("sort-criteria-text");
  sortCriteriaText.textContent = `Sort by ${
    criteria.charAt(0).toUpperCase() +
    criteria.slice(1).replace(/([A-Z])/g, " $1")
  }`; // Capitalize and add space before uppercase letters

  toggleSortDropdown(); // Close the dropdown after sorting
  renderInvestments(); // Re-render the list with sorted data
}

/**
 * Deletes a specific transaction from an investment.
 * @param {string} investmentId - The ID of the parent investment.
 * @param {string} transactionId - The ID of the transaction to delete.
 */
function deleteTransaction(investmentId, transactionId) {
  const investmentIndex = investments.findIndex(
    (inv) => inv.id === investmentId
  );

  if (investmentIndex !== -1) {
    // Filter out the transaction to be deleted
    investments[investmentIndex].purchases = investments[
      investmentIndex
    ].purchases.filter((purchase) => purchase.transactionId !== transactionId);

    // If all purchases are deleted for an investment, remove the investment itself
    if (investments[investmentIndex].purchases.length === 0) {
      investments.splice(investmentIndex, 1);
      if (expandedInvestmentId === investmentId) {
        expandedInvestmentId = null; // Collapse if the deleted investment was expanded
      }
    } else {
      // Re-calculate total quantity for the investment if a purchase was deleted
      investments[investmentIndex].quantity = investments[
        investmentIndex
      ].purchases.reduce((sum, p) => sum + p.quantity, 0);
      // Recalculate total gain for the investment
      calculateInvestmentAggregates();
    }

    // Re-render the investments to reflect the deletion
    renderInvestments();

    // --- Placeholder for API call to delete the transaction on your backend ---
    console.log(
      `Attempting to delete transaction: ${transactionId} for investment: ${investmentId}`
    );

    fetch(`/api/transactions/${transactionId}`, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
      },
    })
      .then((response) => {
        if (!response.ok) {
          console.error("Failed to delete transaction on backend");
        } else {
          console.log("Transaction deleted successfully on backend");
        }
      })
      .catch((error) => {
        console.error("Error during API call for deletion:", error);
      });
  }
}

/**
 * Renders the investment list into the DOM.
 */
function renderInvestments() {
  const investmentListContainer = document.getElementById("investment-list");
  investmentListContainer.innerHTML = ""; // Clear existing content

  // Use the globally sorted 'investments' array
  investments.forEach((investment) => {
    const isExpanded = expandedInvestmentId === investment.id;

    // Determine which gain to display based on currentGainView
    const displayGain =
      currentGainView === "day" ? investment.dayGain : investment.totalGain;
    const displayGainPercent =
      currentGainView === "day"
        ? investment.dayGainPercent
        : investment.totalGainPercent;

    // Create the main investment card container
    const investmentCard = document.createElement("div");
    investmentCard.className = "bg-white hover:bg-gray-50";

    // Create the accordion header (summary row)
    const header = document.createElement("div");
    header.className =
      "grid grid-cols-12 items-center py-4 px-6 cursor-pointer";
    header.onclick = () => toggleExpand(investment.id); // Attach click listener

    header.innerHTML = `
                    <div class="col-span-4 flex items-center">
                        <div class="w-8 h-8 flex items-center justify-center bg-gray-200 rounded-full mr-3 text-sm font-bold text-gray-700">
                            ${investment.symbol.charAt(0)}
                        </div>
                        <div>
                            <div class="font-semibold text-gray-900">${
                              investment.symbol
                            }</div>
                            <div class="text-sm text-gray-500">${
                              investment.name
                            }</div>
                        </div>
                    </div>
                    <div class="col-span-2 text-right text-gray-800 font-medium">
                        ${formatCurrency(investment.price)}
                    </div>
                    <div class="col-span-2 text-right text-gray-800 font-medium">
                        ${investment.quantity.toFixed(4)}
                    </div>
                    <div class="col-span-2 text-right font-medium ${getChangeStyle(
                      displayGain
                    )}">
                        ${displayGain > 0 ? "+" : ""}${formatCurrency(
      displayGain
    )}
                        <span class="ml-1 text-xs"><span class="day-gain-percent-box">${getArrowIcon(
                          displayGainPercent
                        )}${formatPercentage(
      Math.abs(displayGainPercent)
    )}</span></span>
                    </div>
                    <div class="col-span-2 text-right text-gray-800 font-medium flex items-center justify-end">
                        ${formatCurrency(investment.value)}
                        <span class="ml-4 text-gray-400">
                            <svg class="w-5 h-5 transition-transform duration-300 ${
                              isExpanded ? "rotate-180" : ""
                            }" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                        </span>
                    </div>
                `;
    investmentCard.appendChild(header);

    // Create the accordion body (details section) if expanded
    if (isExpanded) {
      const body = document.createElement("div");
      body.className =
        "px-6 pb-4 pt-2 bg-gray-50 border-t border-gray-200 transition-all duration-300 ease-in-out";

      // Purchase History Header
      body.innerHTML += `
                        <div class="grid grid-cols-12 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                            <div class="col-span-3">Purchase Date</div>
                            <div class="col-span-2 text-right">Purchase Price</div>
                            <div class="col-span-2 text-right">Quantity</div>
                            <div class="col-span-3 text-right">Total Gain</div>
                            <div class="col-span-1 text-right">Value</div>
                            <div class="col-span-1 text-right"></div> </div>
                    `;

      // Individual Purchase Records
      investment.purchases.forEach((purchase) => {
        const purchaseRow = document.createElement("div");
        purchaseRow.className =
          "grid grid-cols-12 items-center py-2 text-sm text-gray-800";
        purchaseRow.innerHTML = `
                            <div class="col-span-3">${purchase.date}</div>
                            <div class="col-span-2 text-right">${formatCurrency(
                              purchase.purchasePrice
                            )}</div>
                            <div class="col-span-2 text-right">${purchase.quantity.toFixed(
                              4
                            )}</div>
                            <div class="col-span-3 text-right font-medium ${getChangeStyle(
                              purchase.totalGain
                            )}">
                                ${
                                  purchase.totalGain > 0 ? "+" : ""
                                }${formatCurrency(purchase.totalGain)}
                                <span class="ml-1"><span class="">${getArrowIcon(
                                  purchase.totalGainPercent
                                )}${formatPercentage(
          Math.abs(purchase.totalGainPercent)
        )}</span></span>
                            </div>
                            <div class="col-span-1 text-right font-medium">${formatCurrency(
                              purchase.value
                            )}</div>
                            <div class="col-span-1 text-right">
                                <button class="delete-transaction-btn text-gray-400 hover:text-red-600 ml-2 p-1 rounded-full hover:bg-gray-200"
                                    data-investment-id="${investment.id}"
                                    data-transaction-id="${
                                      purchase.transactionId
                                    }"
                                    title="Delete transaction">
                                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                                </button>
                            </div>
                        `;
        body.appendChild(purchaseRow);
      });
      investmentCard.appendChild(body);
    }

    investmentListContainer.appendChild(investmentCard);
  });

  // After rendering, attach event listeners to all new delete buttons
  document.querySelectorAll(".delete-transaction-btn").forEach((button) => {
    button.addEventListener("click", (event) => {
      // Stop propagation to prevent the accordion from toggling
      event.stopPropagation();
      const investmentId = event.currentTarget.dataset.investmentId;
      const transactionId = event.currentTarget.dataset.transactionId;
      deleteTransaction(investmentId, transactionId);
    });
  });
}

/**
 * Calculates the total gain and total gain percentage for each investment.
 * This function should be called after initial data load and any data updates.
 */
function calculateInvestmentAggregates() {
  investments.forEach((investment) => {
    let totalPurchasedQuantity = 0;
    let totalCostBasis = 0;

    investment.purchases.forEach((purchase) => {
      totalPurchasedQuantity += purchase.quantity;
      totalCostBasis += purchase.purchasePrice * purchase.quantity;
    });

    // Use the current price (investment.price) and total quantity to calculate current value
    const currentValue = investment.price * totalPurchasedQuantity;

    investment.totalPurchasedQuantity = totalPurchasedQuantity; // Store for clarity
    investment.totalCostBasis = totalCostBasis; // Store for clarity

    // Calculate actual total gain and percentage
    if (totalCostBasis > 0) {
      investment.totalGain = currentValue - totalCostBasis;
      investment.totalGainPercent =
        (investment.totalGain / totalCostBasis) * 100;
    } else {
      investment.totalGain = 0;
      investment.totalGainPercent = 0;
    }
  });
}

/**
 * Renders the 401k balance component with current data.
 */
function render401kBalance() {
  document.getElementById("401k-balance").textContent = formatCurrency(
    four01kData.balance
  );
  document.getElementById("401k-timestamp").textContent = four01kData.timestamp;

  const dayChangeElement = document.getElementById("401k-day-change");
  const dayPercentElement = document.getElementById("401k-day-percent");
  const totalGainElement = document.getElementById("401k-total-gain");
  const totalPercentElement = document.getElementById("401k-total-percent");

  // Day Gain
  const dayChangeStyle = getChangeStyle(four01kData.dayChange);
  const daySign = four01kData.dayChange > 0 ? "+" : "";
  dayChangeElement.textContent = `${daySign}${formatCurrency(
    Math.abs(four01kData.dayChange)
  )}`;
  dayChangeElement.className = `text-lg font-bold ${dayChangeStyle}`; // Removed ml-3, applied directly to span
  dayPercentElement.textContent = `${daySign}${formatPercentage(
    Math.abs(four01kData.dayPercent)
  )}`;
  dayPercentElement.className = `ml-2 text-base font-medium ${dayChangeStyle}`;

  // Total Gain
  const totalGainStyle = getChangeStyle(four01kData.totalGain);
  const totalSign = four01kData.totalGain > 0 ? "+" : "";
  totalGainElement.textContent = `${totalSign}${formatCurrency(
    Math.abs(four01kData.totalGain)
  )}`;
  totalGainElement.className = `text-lg font-bold ${totalGainStyle}`;
  totalPercentElement.textContent = `${totalSign}${formatPercentage(
    Math.abs(four01kData.totalGainPercent)
  )}`;
  totalPercentElement.className = `ml-2 text-base font-medium ${totalGainStyle}`;
}

// Define colors for different portfolio categories
const categoryColors = {
  stocks: "#3B82F6", // blue-500
  STOCK: "#3B82F6", // blue-500
  STOCKS: "#3B82F6", // blue-500
  "Common Stock": "#3B82F6", // blue-500
  Crypto: "#F59E0B", // amber-500
  CRYPTO: "#F59E0B", // amber-500
  crypto: "#F59E0B", // amber-500
  ETP: "#A78BFA", // purple-400
  ETF: "#A78BFA", // purple-400
  etf: "#A78BFA", // purple-400
  etf: "#A78BFA", // purple-400
  cash: "#10B981", // emerald-500
  CASH: "#10B981", // emerald-500
};
/**
 * Renders the portfolio highlights section.
 */
function renderPortfolioHighlights() {
  const container = document.getElementById("portfolio-highlights-list");
  container.innerHTML = ""; // Clear existing content

  if (
    four01kData &&
    four01kData.portfolioHighlights &&
    Array.isArray(four01kData.portfolioHighlights)
  ) {
    four01kData.portfolioHighlights.forEach((item) => {
      const div = document.createElement("div");
      const color = categoryColors[item.name] || "#6B7280"; // Default to gray-500 if category not found

      div.className =
        "flex flex-col py-2 px-2 rounded-md hover:bg-gray-50 transition-colors duration-200";
      div.innerHTML = `
                        <div class="flex items-center justify-between mb-1">
                            <div class="flex items-center">
                                <span class="w-3 h-3 rounded-full mr-2" style="background-color: ${color};"></span>
                                <span class="font-medium text-gray-800">${
                                  item.name.charAt(0).toUpperCase() +
                                  item.name.slice(1)
                                }</span>
                            </div>
                            <span class="font-semibold text-gray-900">${formatCurrency(
                              item.value
                            )}</span>
                        </div>
                        <div class="flex items-center justify-between text-sm text-gray-600">
                            <span class="w-1/4">${item.percent.toFixed(
                              1
                            )}%</span>
                            <div class="w-3/4 bg-gray-200 rounded-full h-2 ml-2">
                                <div class="h-full rounded-full" style="width: ${
                                  item.percent
                                }%; background-color: ${color};"></div>
                            </div>
                        </div>
                    `;
      container.appendChild(div);
    });
  }
}

// --- New Transaction Modal Functions ---
const newTransactionModal = document.getElementById("new-transaction-modal");
const addInvestmentBtn = document.getElementById("add-investment-btn");
const closeNewTransactionModalBtn = document.getElementById(
  "close-new-transaction-modal"
);
const cancelNewTransactionBtn = document.getElementById(
  "cancel-new-transaction"
);
const newTransactionForm = document.getElementById("new-transaction-form");
const newTransactionSymbolInput = document.getElementById(
  "new-transaction-symbol"
);
const symbolSuggestionsContainer =
  document.getElementById("symbol-suggestions");

/**
 * Opens the new transaction modal.
 */
function openNewTransactionModal() {
  newTransactionModal.classList.remove("hidden");
  // Set today's date as default for the date input
  document.getElementById("new-transaction-date").valueAsDate = new Date();
}

/**
 * Closes the new transaction modal and resets the form.
 */
function closeNewTransactionModal() {
  newTransactionModal.classList.add("hidden");
  newTransactionForm.reset(); // Clear form fields
  symbolSuggestionsContainer.innerHTML = ""; // Clear suggestions
  symbolSuggestionsContainer.classList.add("hidden"); // Ensure hidden
  selectedSymbolData = null; // Reset selected symbol data
}

/**
 * Fetches symbol suggestions from the Finviz API based on user input.
 * @param {string} input - The user's typed symbol input.
 */
async function fetchSymbolSuggestions(input) {
  const apiUrl = `/api/symbolSuggestion?q=${input}`;
  try {
    const response = await fetch(apiUrl);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json(); // Parse the full response object
    const suggestions = data; // Access the 'result' array

    renderSymbolSuggestions(suggestions);
  } catch (error) {
    console.error("Error fetching symbol suggestions:", error);
    symbolSuggestionsContainer.innerHTML =
      '<div class="p-2 text-red-500">Error fetching suggestions.</div>';
  }
}

/**
 * Renders the fetched symbol suggestions in the dropdown.
 * @param {Array<Object>} suggestions - An array of symbol suggestion objects.
 */
function renderSymbolSuggestions(suggestions) {
  console.log(suggestions);
  symbolSuggestionsContainer.innerHTML = "";
  symbolSuggestionsContainer.classList.remove("hidden");
  if (suggestions && suggestions.length > 0) {
    suggestions.forEach((sug) => {
      const div = document.createElement("div");
      // Use displaySymbol for the text and ticker, and description for company
      div.className =
        "p-2 cursor-pointer hover:bg-blue-100 border-b border-gray-100 last:border-b-0";
      div.textContent = `${sug.displaySymbol} - ${sug.description}`;
      div.dataset.symbol = sug.symbol; // Store the actual symbol for backend use
      div.dataset.description = sug.description; // Store description for company name
      div.dataset.displaySymbol = sug.displaySymbol; // Store display symbol for input value

      div.addEventListener("click", () => {
        newTransactionSymbolInput.value = sug.displaySymbol; // Set input to displaySymbol
        selectedSymbolData = {
          symbol: sug.symbol, // Use the 'symbol' for internal data
          company: sug.description,
          exchange: sug.exchange,
          displaySymbol: sug.displaySymbol,
          type: sug.type,
        };
        symbolSuggestionsContainer.innerHTML = ""; // Clear suggestions after selection
        symbolSuggestionsContainer.classList.add("hidden");
      });
      symbolSuggestionsContainer.appendChild(div);
    });
  } else {
    symbolSuggestionsContainer.innerHTML =
      '<div class="p-2 text-gray-500">No suggestions found.</div>';
  }
}

/**
 * Displays a custom message box instead of alert().
 * @param {string} message - The message to display.
 * @param {string} type - The type of message ('info', 'success', 'error').
 */
function showMessageBox(message, type = "info") {
  const msgBox = document.getElementById("message-box");
  const msgTitle = document.getElementById("message-box-title");
  const msgContent = document.getElementById("message-box-content");
  const msgCloseBtn = document.getElementById("message-box-close");

  msgTitle.textContent = type === "error" ? "Error" : "Success";
  msgTitle.className = `text-lg font-semibold mb-3 ${
    type === "error" ? "text-red-600" : "text-green-600"
  }`;
  msgContent.textContent = message;

  msgBox.classList.remove("hidden");

  msgCloseBtn.onclick = () => {
    msgBox.classList.add("hidden");
  };
}

/**
 * Handles the submission of the new transaction form.
 * @param {Event} event - The form submission event.
 */
function submitNewTransaction(event) {
  event.preventDefault(); // Prevent default form submission

  const symbol = newTransactionSymbolInput.value.trim().toUpperCase();
  const date = document.getElementById("new-transaction-date").value;
  const costBasis = parseFloat(
    document.getElementById("new-transaction-cost-basis").value
  );
  const quantity = parseFloat(
    document.getElementById("new-transaction-quantity").value
  );

  if (
    !symbol ||
    !date ||
    isNaN(costBasis) ||
    isNaN(quantity) ||
    quantity <= 0 ||
    costBasis <= 0
  ) {
    showMessageBox(
      "Please fill all fields correctly. Quantity and Cost Basis must be positive numbers.",
      "error"
    );
    return;
  }
  if (!selectedSymbolData?.type) {
    showMessageBox(
      "Please select a company from the dropdown. We apologize if your ticker is not supported.",
      "error"
    );
    return;
  }

  // Use selectedSymbolData for the actual symbol and company name
  const actualSymbol = selectedSymbolData ? selectedSymbolData.symbol : symbol;
  const companyName = selectedSymbolData
    ? selectedSymbolData.company
    : "Unknown Company";
  const symbolType = selectedSymbolData.type;

  // Find the investment to add the purchase to, or create a new one
  let investmentToUpdate = investments.find(
    (inv) => inv.symbol === actualSymbol
  );

  if (!investmentToUpdate) {
    // Create a new investment entry if the symbol doesn't exist
    investmentToUpdate = {
      id: "inv-" + actualSymbol.toLowerCase() + "-" + Date.now(), // Unique ID for new investment
      symbol: actualSymbol,
      name: companyName,
      price: 0, // Placeholder, would need a real-time price fetch
      quantity: 0, // Will be updated below
      dayGain: 0, // Placeholder
      dayGainPercent: 0, // Placeholder
      value: 0, // Placeholder
      purchases: [],
    };
    investments.push(investmentToUpdate);
  }

  const newPurchase = {
    date: date,
    purchasePrice: costBasis,
    quantity: quantity,
    companyName: companyName,
    symbol: actualSymbol,
  };

  investmentToUpdate.purchases.push(newPurchase);

  // Update the overall investment quantity based on all purchases
  investmentToUpdate.quantity = investmentToUpdate.purchases.reduce(
    (sum, p) => sum + p.quantity,
    0
  );

  // Recalculate aggregates for the updated investment
  calculateInvestmentAggregates();

  // Sort investments again to ensure new ones are in correct order
  sortInvestments(currentSortCriteria); // Re-sort after adding to maintain order

  // --- Placeholder for API call to save the new transaction on your backend ---
  console.log(
    "New transaction to save:",
    newPurchase,
    "for investment:",
    investmentToUpdate.id
  );

  fetch("/api/add_transaction", {
    // Replace with your actual API endpoint
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      // Add any necessary authorization headers here
    },
    body: JSON.stringify({
      date: date,
      cost_basis: costBasis,
      quantity: quantity,
      company_name: companyName,
      symbol: actualSymbol,
      type: symbolType,
    }),
  })
    .then((response) => {
      if (!response.ok) {
        console.error("Failed to save transaction on backend");
        // Handle error: e.g., show error message, or revert local changes
      } else {
        console.log(response.text);
      }
    })
    .catch((error) => {
      console.error("Error during API call for saving transaction:", error);
    });

  showMessageBox("Transaction added successfully!", "success");
  closeNewTransactionModal();
}

// Function to fetch data and render, which will be called repeatedly
async function pollInvestments() {
  console.log("Fetching investments..."); // For debugging
  const apiData =
    investments.length < 1
      ? await fetchPortfolioDataOnFirstLoad()
      : await fetchDataFromAPI();
  if (apiData.positions.length > 0) {
    // Only update if data was successfully fetched
    // Clear the existing sample data and populate with API data
    console.log(apiData.positions);
    console.log(apiData);
    investments.splice(0, investments.length, ...apiData.positions); // Add all fetched data
    four01kData = apiData;
    calculateInvestmentAggregates(); // Recalculate aggregates for new API data
    renderInvestments(); // Re-render the list with updated data
    render401kBalance(); // Update 401k balance as well
    renderPortfolioHighlights(); // Update portfolio highlights
  }
  // Schedule the next fetch after 10 seconds (10000 milliseconds)
  // This ensures the next call starts 10 seconds *after the current one finishes*
  setTimeout(pollInvestments, 20000);
}

// Initial render when the DOM is fully loaded
document.addEventListener("DOMContentLoaded", () => {
  // Start the polling process when the page loads
  pollInvestments();

  // Attach event listeners to gain view dropdown button
  document
    .getElementById("gain-view-button")
    .addEventListener("click", toggleGainViewDropdown);

  // Attach event listeners to gain view dropdown items
  document
    .querySelectorAll("#gain-view-dropdown-menu button")
    .forEach((button) => {
      button.addEventListener("click", (event) => {
        const gainType = event.target.dataset.gainType;
        setGainView(gainType);
      });
    });

  // Attach event listener to the sort button
  document
    .getElementById("sort-button")
    .addEventListener("click", toggleSortDropdown);

  // Attach event listeners to dropdown items
  document.querySelectorAll("#sort-dropdown-menu button").forEach((button) => {
    button.addEventListener("click", (event) => {
      const sortBy = event.target.dataset.sortBy;
      sortInvestments(sortBy);
    });
  });

  // Close dropdown when clicking outside
  document.addEventListener("click", (event) => {
    const sortDropdownContainer = document.getElementById(
      "sort-dropdown-container"
    );
    const gainViewDropdownContainer = document.getElementById(
      "gain-view-dropdown-container"
    );

    if (isSortDropdownOpen && !sortDropdownContainer.contains(event.target)) {
      toggleSortDropdown();
    }
    if (
      isGainViewDropdownOpen &&
      !gainViewDropdownContainer.contains(event.target)
    ) {
      toggleGainViewDropdown();
    }
  });

  // --- Event Listeners for New Transaction Modal ---
  addInvestmentBtn.addEventListener("click", openNewTransactionModal);
  closeNewTransactionModalBtn.addEventListener(
    "click",
    closeNewTransactionModal
  );
  cancelNewTransactionBtn.addEventListener("click", closeNewTransactionModal);
  newTransactionForm.addEventListener("submit", submitNewTransaction);

  // Symbol input debounce and suggestions
  newTransactionSymbolInput.addEventListener("input", (event) => {
    clearTimeout(debounceTimer);
    const input = event.target.value;
    if (input.length > 0) {
      debounceTimer = setTimeout(() => {
        fetchSymbolSuggestions(input);
      }, 300); // Debounce for 300ms
    } else {
      symbolSuggestionsContainer.innerHTML = ""; // Clear suggestions if input is empty
    }
  });

  // Close symbol suggestions if clicked outside
  document.addEventListener("click", (event) => {
    if (
      !newTransactionSymbolInput.contains(event.target) &&
      !symbolSuggestionsContainer.contains(event.target)
    ) {
      symbolSuggestionsContainer.innerHTML = "";
    }
  });
});

// Placeholder for API fetch function (for initial data load, if needed)
async function fetchDataFromAPI() {
  try {
    // Replace with your actual API endpoint for initial data
    const response = await fetch("api/portfolio");
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Error fetching initial data:", error);
    return [];
  }
}

async function fetchPortfolioDataOnFirstLoad() {
  try {
    // Replace with your actual API endpoint for initial data
    const response = await fetch("api/cache/portfolio");
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    investments.splice(0, investments.length, ...data.positions); // Add all fetched data
    four01kData = data;
    return data;
  } catch (error) {
    console.error("Error fetching initial data:", error);
    return [];
  }
}

