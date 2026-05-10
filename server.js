const express = require("express");

const app = express();
const PORT = process.env.PORT || 3000;

app.get("/search", (req, res) => {
  const { card } = req.query;
  res.json({ message: "Server working", card: card ?? null });
});

app.listen(PORT, () => {
  console.log(`Server listening on http://localhost:${PORT}`);
});

