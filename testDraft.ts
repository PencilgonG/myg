import { createLolProDraftLinks } from "./src/services/draft/lolprodraft.ts";

(async () => {
  console.log("▶️ testDraft start");
  try {
    const links = await createLolProDraftLinks("Blue", "Red", "TestMatch");
    console.log("✅ Links generated:");
    console.log(links);
  } catch (e) {
    console.error("❌ Error:", e);
  } finally {
    console.log("⏹ done");
  }
})();


