import unittest
from decimal import Decimal

from app.visualization import build_chart_metadata


class VisualizationTests(unittest.TestCase):
    def test_single_numerical_value_unsuitable(self):
        """Case 1: Query that returns a single numerical value (e.g. SELECT COUNT(*))."""
        columns = ["COUNT(*)"]
        rows = [{"COUNT(*)": 5}]
        meta = build_chart_metadata("How many students are in the database?", columns, rows)

        self.assertFalse(meta["suitable"])
        self.assertIn("single scalar value", meta["reason"].lower())

    def test_categories_and_numerical_values(self):
        """Case 2: Query that returns categories and numerical values."""
        columns = ["name", "marks"]
        rows = [
            {"name": "Rahul", "marks": Decimal("85.00")},
            {"name": "Priya", "marks": Decimal("92.00")},
            {"name": "Arjun", "marks": Decimal("78.00")},
        ]
        meta = build_chart_metadata("Display the marks of each student.", columns, rows)

        self.assertTrue(meta["suitable"])
        self.assertEqual(meta["chart_type"], "bar")
        self.assertEqual(meta["x_field"], "name")
        self.assertEqual(meta["y_fields"], ["marks"])
        self.assertEqual(meta["labels"], ["Rahul", "Priya", "Arjun"])
        self.assertEqual(len(meta["datasets"]), 1)
        self.assertEqual(meta["datasets"][0]["data"], [85.0, 92.0, 78.0])
        self.assertIn("bar", meta["available_types"])
        self.assertIn("horizontalBar", meta["available_types"])
        self.assertIn("pie", meta["available_types"])

    def test_several_numerical_columns(self):
        """Case 3: Query that returns several numerical columns."""
        columns = ["course", "min_marks", "max_marks", "avg_marks"]
        rows = [
            {"course": "CSE", "min_marks": 70, "max_marks": 95, "avg_marks": Decimal("82.50")},
            {"course": "ECE", "min_marks": 65, "max_marks": 88, "avg_marks": Decimal("76.50")},
        ]
        meta = build_chart_metadata("Compare student marks per course.", columns, rows)

        self.assertTrue(meta["suitable"])
        self.assertEqual(meta["x_field"], "course")
        self.assertEqual(meta["y_fields"], ["min_marks", "max_marks", "avg_marks"])
        self.assertEqual(len(meta["datasets"]), 3)
        self.assertEqual(meta["datasets"][0]["label"], "Min Marks")
        self.assertEqual(meta["datasets"][1]["label"], "Max Marks")
        self.assertEqual(meta["datasets"][2]["label"], "Average Marks")
        # Pie is not available for multiple metrics
        self.assertNotIn("pie", meta["available_types"])
        self.assertIn("bar", meta["available_types"])
        self.assertIn("line", meta["available_types"])

    def test_empty_result_unsuitable(self):
        """Case 4: Query that returns an empty result."""
        columns = ["name", "marks"]
        rows = []
        meta = build_chart_metadata("Students with marks > 100", columns, rows)

        self.assertFalse(meta["suitable"])
        self.assertIn("no data returned", meta["reason"].lower())

    def test_null_values_handled_gracefully(self):
        """Case 5: Query with null values."""
        columns = ["name", "marks"]
        rows = [
            {"name": "Student A", "marks": None},
            {"name": "Student B", "marks": Decimal("90.00")},
            {"name": None, "marks": Decimal("75.00")},
        ]
        meta = build_chart_metadata("Show marks", columns, rows)

        self.assertTrue(meta["suitable"])
        self.assertEqual(meta["labels"], ["Student A", "Student B", "(empty)"])
        self.assertEqual(meta["datasets"][0]["data"], [None, 90.0, 75.0])

    def test_data_unsuitable_for_visualization(self):
        """Case 6: Query that returns purely non-numerical columns."""
        columns = ["name", "course"]
        rows = [
            {"name": "Rahul", "course": "CSE"},
            {"name": "Priya", "course": "ISE"},
        ]
        meta = build_chart_metadata("List student courses", columns, rows)

        self.assertFalse(meta["suitable"])
        self.assertIn("no numeric metrics", meta["reason"].lower())

    def test_many_categories_defaults_to_horizontal_bar(self):
        """Case 7: Query that returns many categories (> 8)."""
        columns = ["category", "score"]
        rows = [{"category": f"Cat {i}", "score": i * 10} for i in range(15)]
        meta = build_chart_metadata("List all category scores", columns, rows)

        self.assertTrue(meta["suitable"])
        self.assertEqual(meta["chart_type"], "horizontalBar")
        self.assertIn("horizontalBar", meta["available_types"])

    def test_user_explicit_pie_chart_preference(self):
        """Case 8: User explicitly requests a pie chart in question."""
        columns = ["course", "count"]
        rows = [
            {"course": "CSE", "count": 2},
            {"course": "ISE", "count": 1},
            {"course": "ECE", "count": 1},
        ]
        meta = build_chart_metadata("Show the number of students in each course using a pie chart.", columns, rows)

        self.assertTrue(meta["suitable"])
        self.assertEqual(meta["chart_type"], "pie")
        self.assertIn("pie", meta["available_types"])

    def test_user_explicit_horizontal_bar_preference(self):
        """Case 9: User explicitly requests a horizontal bar chart."""
        columns = ["name", "marks"]
        rows = [
            {"name": "Rahul", "marks": 85},
            {"name": "Priya", "marks": 92},
        ]
        meta = build_chart_metadata("Show student marks in a horizontal bar chart", columns, rows)

        self.assertTrue(meta["suitable"])
        self.assertEqual(meta["chart_type"], "horizontalBar")


if __name__ == "__main__":
    unittest.main()
