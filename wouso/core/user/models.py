from datetime import datetime
from django.db import models
from django.contrib.auth.models import User, Group
from wouso.core.god import God
from wouso.core.magic.models import Artifact, Spell

class PlayerGroup(models.Model):
    """ Group players together in a hierchical way """
    # TODO: check if the perms Group linking is of any use
    group = models.ForeignKey(Group, unique=True, related_name="%(class)s_related")
    name = models.CharField(max_length=100)
    gclass = models.IntegerField(default=0)
    parent = models.ForeignKey('PlayerGroup', default=None, null=True, blank=True)

    # used only for sorting and position
    points = models.FloatField(default=0)

    _sisters = []

    @property
    def live_points(self):
        """ Calculate sum of user points dynamically """
        p = self.player_set.aggregate(total=models.Sum('points'))
        if p['total'] is None:
            return 0
        return p['total']

    @property
    def children(self):
        """ All groups with parent set to this group """
        return self.playergroup_set.all()

    @property
    def sisters(self):
        """ All groups with the same parent as this group or of the same
        class, if parent is not set.
        """
        if not self._sisters:
            if self.parent:
                self._sisters = list(self.parent.children.exclude(id=self.id))
            else:
                self._sisters = list(PlayerGroup.objects.filter(gclass=self.gclass).exclude(id=self.id))
        return self._sisters

    def __unicode__(self):
        return self.name

class InsufficientAmount(Exception): pass

class PlayerArtifactAmount(models.Model):
    """ Tie artifact and amount to the owner user """
    class Meta:
        unique_together = ('player', 'artifact')
    player = models.ForeignKey('Player')
    artifact = models.ForeignKey(Artifact)
    amount = models.IntegerField(default=1)

    def __unicode__(self):
        return u"%s has %s [%d]" % (self.player, self.artifact, self.amount)

class PlayerSpellAmount(models.Model):
    """ Tie spells to collecting user """
    class Meta:
        unique_together = ('player', 'spell')
    player = models.ForeignKey('Player')
    spell = models.ForeignKey(Spell)
    amount = models.IntegerField(default=1)

    def __unicode__(self):
        return u"%s has %s [%d]" % (self.player, self.spell, self.amount)

class PlayerSpellDue(models.Model):
    """ Tie spell, casting user, duration with the victim player """
    class Meta:
        unique_together = ('player', 'spell')
    player = models.ForeignKey('Player')
    spell = models.ForeignKey(Spell)
    source = models.ForeignKey('Player', related_name='spell_source')
    due = models.DateTimeField()

    def __unicode__(self):
        return u"%s casted on %s until %s [%s]" % (self.spell, self.player, self.due, self.source)
    
class Player(models.Model):
    """ Base class for the game user. This is extended by game specific
    player models.
    """
    user = models.ForeignKey(User, unique=True,
        related_name="%(class)s_related")

    # Unique differentiator for ladder
    # Do not modify it manually, use scoring.score instead
    points = models.FloatField(default=0, blank=True, null=True)

    level_no = models.IntegerField(default=1, blank=True, null=True)
    #level = models.ForeignKey(Artifact, default=Artifact.get_level_1, related_name='user_level', blank=True, null=True)

    last_seen = models.DateTimeField(null=True, blank=True)

    # artifacts available for using
    artifacts = models.ManyToManyField(Artifact, blank=True, through='PlayerArtifactAmount')
    # spells available for casting
    spells_collection = models.ManyToManyField(Spell, blank=True, through='PlayerSpellAmount', related_name='spell_collection')
    groups = models.ManyToManyField(PlayerGroup, blank=True)

    # spells casted on itself
    # it doesnt work this way, instead provide it as a property
    # see: http://stackoverflow.com/questions/583327/django-model-with-2-foreign-keys-from-the-same-table
    #spells = models.ManyToManyField(Spell, blank=True, through='PlayerSpellDue')
    
    @property
    def spells(self):
        return self.playerspelldue_set.all()
        
    @property
    def level(self):
        """ Return an artifact object for the current level_no.
        Ask God about the right artifact object, given the player instance.
        In the future, God may check players race and give specific artifacts.
        """
        return God.get_user_level(self.level_no, player=self)

    @property
    def coins(self):
        # TODO check usage and deprecate this function
        from wouso.core.scoring.models import History
        return History.user_coins(self.user)

    @property
    def proximate_group(self):
        """ Return the group with minimum class, for which the user
        is a member of, or None.
        """
        res = self.groups.aggregate(gclass=models.Min('gclass'))
        if res['gclass'] is None:
            return None

        return self.groups.filter(gclass=res['gclass'])[0]

    @property
    def artifact_amounts(self):
        return self.playerartifactamount_set

    @property
    def spell_amounts(self):
        return self.playerspellamount_set

    def level_progress(self):
        """ Return a dictionary with: points_gained, points_left, next_level """
        return God.get_level_progress(self)

    def has_modifier(self, modifier):
        """ Check for an artifact with id = modifier
        or for an active spell cast on me with id = modifier
        """
        try:
            return PlayerArtifactAmount.objects.get(player=self, artifact__name=modifier)
        except PlayerArtifactAmount.DoesNotExist:
            pass

        try:
            return PlayerSpellDue.objects.get(player=self, spell__name=modifier)
        except PlayerSpellDue.DoesNotExist:
            pass
        return False

    def use_modifier(self, modifier, amount):
        """ Substract amount of modifier artifact from players collection.
        If the current amount is less than amount, raise an exception.
        If the amount after substraction is zero, delete the corresponding
        artifact amount object.
        """
        paamount = self.has_modifier(modifier)
        if amount > paamount.amount:
            raise InsufficientAmount()

        paamount.amount -= amount
        if paamount.amount == 0:
            paamount.delete()
        else:
            paamount.save()
        return paamount

    def give_modifier(self, modifier, amount):
        """ Add given amount to existing, or creat new artifact amount
        for the current user.
        """
        if amount <= 0:
            return

        paamount = self.has_modifier(modifier)
        if not paamount:
            artifact = God.get_artifact_for_modifier(modifier, self)
            paamount = PlayerArtifactAmount.objects.create(player=self, artifact=artifact, amount=amount)
        else:
            paamount.amount += amount
            paamount.save()
        return paamount

    def add_spell(self, spell):
        """ Add a spell to self collection """
        try:
            psamount = PlayerSpellAmount.objects.get(player=self, spell=spell)
        except PlayerSpellAmount.DoesNotExist:
            psamount = PlayerSpellAmount.objects.create(player=self, spell=spell)
            return
        psamount.amount += 1
        psamount.save()

    def cast_spell(self, spell, source, due):
        """ Curse self with given spell from source, for due time. """
        try:
            psamount = PlayerSpellAmount.objects.get(player=source, spell=spell)
            assert psamount.amount > 0
        except (PlayerSpellAmount.DoesNotExist, AssertionError):
            return False
        try:
            psdue = PlayerSpellDue.objects.create(player=self, source=source, spell=spell, due=due)
            # Post-cast God action (there are specific modifiers, such as clean-spells
            # that are implemented in God
            God.post_cast(psdue)
            psamount.amount -= 1
            if psamount.amount == 0:
                psamount.delete()
            else:
                psamount.save()
            return True
        except:
            return False

    # special:

    def get_extension(self, cls):
        """ Search for an extension of this object, with the type cls
        Create instance if there isn't any.

        Using an workaround, while: http://code.djangoproject.com/ticket/7623 gets fixed.
        Also see: http://code.djangoproject.com/ticket/11618
        """
        try:
            extension = cls.objects.get(user=self.user)
        except cls.DoesNotExist:
            extension = cls(player_ptr = self)
            for f in self._meta.local_fields:
                setattr(extension, f.name, getattr(self, f.name))
            extension.save()

        return extension

    def __unicode__(self):
        return u"%s %s" % (self.user.first_name, self.user.last_name)

# Hack for having user and user's profile always in sync
def user_post_save(sender, instance, **kwargs):
    profile, new = Player.objects.get_or_create(user=instance)
models.signals.post_save.connect(user_post_save, User)
