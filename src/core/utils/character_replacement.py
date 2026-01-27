"""
Character Replacement Module
============================

Special character replacement utilities for output file compatibility.

This is the canonical location for character replacement.
For backward compatibility, this is also re-exported from:
- common.utils
- txr_replay_core.utils
"""


class CharacterReplacement:
    """
    Handle special character replacements for output files.
    
    Used primarily in Phase 2 processing where colons in corrections
    need to be replaced with the NOT SIGN character (¬) for compatibility.
    
    Example:
        >>> CharacterReplacement.colon_to_not_sign("Field1:Value1")
        'Field1¬Value1'
        >>> CharacterReplacement.not_sign_to_colon("Field1¬Value1")
        'Field1:Value1'
    """
    
    @staticmethod
    def colon_to_not_sign(value: str) -> str:
        """
        Replace colons with NOT SIGN character (¬).
        
        Args:
            value: String value to process
            
        Returns:
            String with colons replaced by chr(172) (¬)
            
        Note:
            Using chr(172) instead of Unicode to prevent encoding issues.
            Returns original value unchanged if it's a special marker.
        """
        if not value or value in ["No Change", "Client not found", "Processing Error"]:
            return value
        # Use ASCII character replacement to avoid encoding issues
        return value.replace(':', chr(172))  # chr(172) = ¬ (NOT SIGN)
    
    @staticmethod
    def not_sign_to_colon(value: str) -> str:
        """
        Reverse replacement: NOT SIGN back to colon.
        
        Args:
            value: String value to process
            
        Returns:
            String with NOT SIGN replaced by colons
        """
        if not value:
            return value
        return value.replace(chr(172), ':')
