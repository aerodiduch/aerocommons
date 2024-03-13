class FacebookParser:
    """
    A class that parses Facebook messages and interactions.

    Attributes:
        request (dict): The request object containing the Facebook
        message data.

    Properties:
        message_type (str): The type of the Facebook message.
        message_number (str): The sender of the Facebook message.
        message_text (str): The text content of the Facebook message.
        interaction_type (str): The type of the Facebook interaction.
        interaction_id (str): The ID of the Facebook interaction.
    """

    def __init__(self, request):
        self.request = request
        self.MESSAGE_ROOT = (
            self.request.get("entry")[0]
            .get("changes")[0]
            .get("value")
            .get("messages")[0]
        )

    def __str__(self):
        return str(self.request)

    def to_dict(self):
        """
        Converts the request object to a dictionary.

        Returns:
            dict: The request object as a dictionary.
        """
        return self.request

    @property
    def message_type(self):
        """
        Get the type of the Facebook message.

        Returns:
            str: The type of the Facebook message.
        """
        return self.MESSAGE_ROOT.get("type")

    @property
    def message_number(self):
        """
        Get the sender of the Facebook message.

        Returns:
            str: The sender of the Facebook message.
        """
        return self.MESSAGE_ROOT.get("from")

    @property
    def message_text(self):
        """
        Get the text content of the Facebook message.

        Returns:
            str: The text content of the Facebook message.
        """
        if self.message_type == "text":
            return self.MESSAGE_ROOT.get("text").get("body")
        elif self.message_type == "interactive":
            return self.MESSAGE_ROOT.get("interactive").get("text")

        return None

    @property
    def interaction_type(self):
        """
        Get the type of the Facebook interaction.

        Returns:
            str: The type of the Facebook interaction.
        """
        if self.message_type == "interactive":
            return self.MESSAGE_ROOT.get("interactive").get("type")
        return None

    @property
    def interaction_id(self):
        """
        Get the ID of the Facebook interaction.

        Returns:
            str: The ID of the Facebook interaction.
        """
        if self.interaction_type == "list_reply":
            return self.MESSAGE_ROOT.get("interactive").get("list_reply").get("id")

        return None

    @property
    def is_text(self):
        """
        Check if the Facebook message is a text message.

        Returns:
            bool: True if the message is a text message, False otherwise.
        """
        return self.message_type == "text"

    @property
    def is_interactive(self):
        """
        Check if the Facebook message is an interactive message.

        Returns:
            bool: True if the message is an interactive message, False otherwise.
        """
        return self.message_type == "interactive"
