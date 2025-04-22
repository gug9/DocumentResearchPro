import unittest
from unittest.mock import patch

from planner import ResearchPlanner
from models import ResearchPlan, ResearchQuestion, ResearchTask


class TestResearchPlanner(unittest.TestCase):
    """Tests for the ResearchPlanner class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.planner = ResearchPlanner()
    
    def test_extract_topics(self):
        """Test the _extract_topics method."""
        prompt = "Confronto framework cybersecurity UE 2018-2023"
        topics = self.planner._extract_topics(prompt)
        
        # Check that relevant topics are extracted
        self.assertIn("cybersecurity", topics)
        self.assertIn("frameworks", topics)
        self.assertIn("european union", topics)
        
        # Check that years are extracted
        self.assertIn("years 2018-2023", topics)
    
    def test_generate_questions(self):
        """Test the _generate_questions method."""
        prompt = "Confronto framework cybersecurity UE 2018-2023"
        topics = ["cybersecurity", "frameworks", "european union"]
        
        questions = self.planner._generate_questions(topics, prompt)
        
        # Check that we have questions
        self.assertGreater(len(questions), 0)
        
        # Check that each question has sources
        for question in questions:
            self.assertIn("question", question)
            self.assertIn("sources", question)
            self.assertGreater(len(question["sources"]), 0)
    
    def test_determine_depth(self):
        """Test the _determine_depth method."""
        # Short prompt should return depth 1
        self.assertEqual(self.planner._determine_depth("Short prompt"), 1)
        
        # Medium prompt should return depth 2
        self.assertEqual(self.planner._determine_depth("This is a medium length prompt that should be classified as depth 2."), 2)
        
        # Long prompt should return depth 3
        long_prompt = "This is a very detailed prompt that should definitely be classified as depth 3. " * 3
        self.assertEqual(self.planner._determine_depth(long_prompt), 3)
        
        # Prompt with 'detailed' keyword should return depth 3
        self.assertEqual(self.planner._determine_depth("Please provide a detailed analysis."), 3)
    
    def test_create_research_plan(self):
        """Test the create_research_plan method."""
        prompt = "Confronto framework cybersecurity UE 2018-2023"
        
        plan = self.planner.create_research_plan(prompt)
        
        # Check that we get a valid plan
        self.assertIsInstance(plan, ResearchPlan)
        self.assertGreater(len(plan.questions), 0)
        self.assertIn(plan.depth, [1, 2, 3])
        
        # Check that each question is properly structured
        for question in plan.questions:
            self.assertIsInstance(question, ResearchQuestion)
            self.assertTrue(question.question)
            self.assertIsInstance(question.sources, list)
    
    def test_create_research_task(self):
        """Test the create_research_task method."""
        prompt = "Confronto framework cybersecurity UE 2018-2023"
        
        task = self.planner.create_research_task(prompt)
        
        # Check that we get a valid task
        self.assertIsInstance(task, ResearchTask)
        self.assertEqual(task.objective, prompt)
        self.assertGreater(len(task.sources), 0)
        self.assertIn(task.depth, [1, 2, 3])
        self.assertEqual(task.status, "ready")
        
        # Check that task has a valid ID
        self.assertTrue(task.task_id)


if __name__ == '__main__':
    unittest.main()
