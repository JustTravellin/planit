// One entry per shareable list. Every tab here maps straight onto a
// collection the backend already treats generically, so adding a new kind
// of list to the planner later is just adding an entry to this file.
export const TABS = [
  {
    key: "runsheet",
    label: "Run Sheet",
    blurb: "The timed plan for the day, phase by phase.",
    sortBy: "time",
    fields: [
      { name: "time", label: "Time", type: "text", placeholder: "16:00", width: "small" },
      {
        name: "phase",
        label: "Phase",
        type: "select",
        options: ["Arrival", "Golden hour", "Evening", "Wind-down", "Other"],
      },
      { name: "title", label: "What happens", type: "text" },
      { name: "description", label: "Details", type: "textarea" },
      { name: "owner", label: "Who's on it", type: "text" },
    ],
  },
  {
    key: "zones",
    label: "Zones & Layout",
    blurb: "Every space guests can gather in, and its weather fallback.",
    fields: [
      { name: "name", label: "Zone name", type: "text", placeholder: "Bar & anchor tent" },
      {
        name: "type",
        label: "Type",
        type: "select",
        options: ["Anchor / main tent", "Lounge", "Bar", "Dining", "Dance floor", "Fireside", "Games", "Photo spot", "Other"],
      },
      { name: "capacity", label: "Capacity", type: "number", width: "small" },
      { name: "notes", label: "Notes", type: "textarea" },
      { name: "weatherFallback", label: "If it rains / is windy", type: "textarea" },
    ],
  },
  {
    key: "guests",
    label: "Guests",
    blurb: "Who's coming, and anything you need to know before they arrive.",
    sortBy: "name",
    fields: [
      { name: "name", label: "Name", type: "text" },
      { name: "contact", label: "Contact", type: "text", placeholder: "phone or email" },
      { name: "rsvp", label: "RSVP", type: "select", options: ["Pending", "Yes", "No"] },
      { name: "plusOne", label: "Plus one", type: "checkbox" },
      { name: "dietary", label: "Dietary / access needs", type: "text" },
      { name: "zone", label: "Seating / zone", type: "text" },
    ],
  },
  {
    key: "vendors",
    label: "Vendors & Budget",
    blurb: "Everything hired or booked, and what it costs.",
    summary: (items) => {
      const num = (v) => Number(v) || 0;
      const estimated = items.reduce((sum, i) => sum + num(i.costEstimate), 0);
      const actual = items.reduce((sum, i) => sum + num(i.costActual), 0);
      const outstandingDeposits = items.filter((i) => i.costEstimate && !i.depositPaid).length;
      return [
        { label: "Estimated total", value: `$${estimated.toLocaleString()}` },
        { label: "Actual / booked total", value: `$${actual.toLocaleString()}` },
        { label: "Deposits still owing", value: outstandingDeposits },
      ];
    },
    fields: [
      {
        name: "category",
        label: "Category",
        type: "select",
        options: [
          "Marquee / tent",
          "Catering",
          "Bar",
          "Furniture hire",
          "Toilet hire",
          "Florist",
          "Lighting / festoon",
          "Dance floor",
          "Sound / PA",
          "Transport / minibus",
          "Photography",
          "Other",
        ],
      },
      { name: "name", label: "Vendor", type: "text" },
      { name: "contact", label: "Contact", type: "text" },
      { name: "costEstimate", label: "Estimated ($)", type: "number", width: "small" },
      { name: "costActual", label: "Actual ($)", type: "number", width: "small" },
      { name: "depositPaid", label: "Deposit paid", type: "checkbox" },
      {
        name: "status",
        label: "Status",
        type: "select",
        options: ["To book", "Booked", "Confirmed", "Delivered / done"],
      },
      { name: "notes", label: "Notes", type: "textarea" },
    ],
  },
  {
    key: "shopping",
    label: "Shopping List",
    blurb: "Glassware, vases, cloths, decor — buy it, hire it, or borrow it.",
    fields: [
      { name: "item", label: "Item", type: "text" },
      { name: "source", label: "Source", type: "select", options: ["Buy", "Hire", "Borrow"] },
      { name: "quantity", label: "Qty", type: "text", width: "small" },
      { name: "assignee", label: "Who's getting it", type: "text" },
      {
        name: "status",
        label: "Status",
        type: "select",
        options: ["To source", "Collected", "Returned"],
      },
      { name: "returnBy", label: "Return by", type: "date" },
    ],
  },
  {
    key: "tasks",
    label: "Tasks",
    blurb: "Permits, pest control, parking, insurance — the jobs someone needs to own.",
    fields: [
      { name: "title", label: "Task", type: "text" },
      {
        name: "category",
        label: "Category",
        type: "select",
        options: [
          "Permits & siting approval",
          "Bugs & pest control",
          "Fire season / CFA",
          "Parking & transport",
          "Toilets",
          "Insurance & neighbours",
          "Weather contingency",
          "Other",
        ],
      },
      { name: "assignee", label: "Assigned to", type: "text" },
      { name: "dueDate", label: "Due", type: "date" },
      { name: "status", label: "Status", type: "select", options: ["To do", "In progress", "Done"] },
    ],
  },
  {
    key: "contacts",
    label: "Contacts",
    blurb: "Every vendor and helper's number in one place, for the day itself.",
    fields: [
      { name: "name", label: "Name", type: "text" },
      { name: "role", label: "Role", type: "text", placeholder: "Marquee hire, MC, driver..." },
      { name: "phone", label: "Phone", type: "text" },
      { name: "email", label: "Email", type: "text" },
      { name: "notes", label: "Notes", type: "textarea" },
    ],
  },
];
